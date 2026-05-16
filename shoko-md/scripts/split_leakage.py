#!/usr/bin/env python3
from qc_utils import *
try:
    from dedup_near import datasketch_clusters, fallback_clusters
except Exception:
    datasketch_clusters = None
    fallback_clusters = None


def collect_splits(paths: List[str], cfg: Dict[str, Any]) -> Dict[str, List[Tuple[Dict[str, Any], Any]]]:
    splits: Dict[str, List[Tuple[Dict[str, Any], Any]]] = defaultdict(list)
    for path in paths:
        for wrapped in iter_records(path, allow_json_errors=True):
            rec = wrapped.record
            if is_synthetic_record(rec):
                # Blank/unparseable rows hash alike; including them would report
                # spurious cross-split leakage. validate_schema flags them instead.
                continue
            split = None
            if isinstance(rec, dict) and rec.get("split") is not None:
                split = str(rec.get("split")).strip().lower()
                if split in {"validation", "valid"}:
                    split = "val"
            if not split:
                split = split_name_from_path(path)
            splits[split].append((wrapped.loc, rec))
    return splits


def exact_leakage(splits: Dict[str, List[Tuple[Dict[str, Any], Any]]], sample_size: int) -> Tuple[int, List[Dict[str, Any]]]:
    seen: Dict[str, Tuple[str, Dict[str, Any], Any]] = {}
    count = 0
    examples: List[Dict[str, Any]] = []
    for split, rows in splits.items():
        for loc, rec in rows:
            h = record_hash(rec)
            if h in seen and seen[h][0] != split:
                count += 1
                if len(examples) < sample_size:
                    prev_split, prev_loc, prev_rec = seen[h]
                    examples.append({"hash": h, "split_a": prev_split, "loc_a": prev_loc, "split_b": split, "loc_b": loc, "sample": sanitize_sample(rec)})
            else:
                seen[h] = (split, loc, rec)
    return count, examples


def near_leakage(splits: Dict[str, List[Tuple[Dict[str, Any], Any]]], cfg: Dict[str, Any], sample_size: int) -> Tuple[int, List[Dict[str, Any]], str]:
    threshold = float(cfg.get("near_duplicate_threshold", 0.85))
    max_per_split = int(cfg.get("split_near_leakage_max_records_per_split", 50000))
    flat: List[Tuple[Dict[str, Any], str]] = []
    split_for_idx: List[str] = []
    truncated = []
    for split, rows in splits.items():
        if len(rows) > max_per_split:
            truncated.append(split)
        for loc, rec in rows[:max_per_split]:
            flat.append((loc, primary_input_text(rec)))
            split_for_idx.append(split)
    if len(flat) < 2:
        return 0, [], "not_enough_records"
    try:
        if datasketch_clusters is None:
            raise RuntimeError("datasketch import unavailable")
        clusters, method = datasketch_clusters(flat, threshold, int(cfg.get("near_duplicate_num_perm", 128)))
    except Exception:
        if fallback_clusters is None:
            return 0, [], "unavailable"
        try:
            clusters, method = fallback_clusters(flat, threshold, int(cfg.get("near_duplicate_fallback_max_records", 5000)))
        except Exception as exc:
            return 0, [], f"unavailable:{exc}"
    cross = []
    for group in clusters:
        splitset = {split_for_idx[i] for i in group}
        if len(splitset) > 1:
            cross.append(group)
    examples = []
    for group in cross[:sample_size]:
        examples.append({
            "size": len(group),
            "splits": sorted({split_for_idx[i] for i in group}),
            "members": [{"split": split_for_idx[i], "loc": flat[i][0], "input_excerpt": redact_text(flat[i][1][:250])} for i in group[:sample_size]],
        })
    method = method + (f"; truncated splits over {max_per_split}: {truncated}" if truncated else "")
    return len(cross), examples, method


def main() -> int:
    parser = common_parser("Detect exact and near leakage across train/val/test/dev splits", multiple_inputs=True)
    args = parser.parse_args()
    cfg = load_config(args.config)
    sample_size = args.sample_size or cfg.get("sample_size", 5)
    files = []
    for inp in (args.input if isinstance(args.input, list) else [args.input]):
        files.extend(list_input_files(inp))
    try:
        splits = collect_splits(files, cfg)
        exact_count, exact_examples = exact_leakage(splits, sample_size)
        near_count, near_examples, near_method = near_leakage(splits, cfg, sample_size)
    except Exception as exc:
        out = {"script": "split_leakage.py", "timestamp": now_iso(), "summary": check_result("split_leakage", "CRITICAL", str(exc)), "error": str(exc)}
        emit_json(out)
        return 2
    split_counts = {k: len(v) for k, v in splits.items()}
    if exact_count:
        severity = "CRITICAL"
        finding = f"{exact_count} exact cross-split leak(s); {near_count} near cross-split cluster(s)"
    elif near_count:
        severity = "WARNING"
        finding = f"{near_count} near-duplicate cross-split cluster(s); no exact leakage"
    else:
        severity = "OK"
        finding = "No exact or near cross-split leakage found"
    eprint(f"[{severity}] split_leakage: splits={split_counts}; {finding}")
    out = {
        "script": "split_leakage.py",
        "timestamp": now_iso(),
        "files": files,
        "split_counts": split_counts,
        "exact_leakage_count": exact_count,
        "exact_examples": exact_examples,
        "near_leakage_cluster_count": near_count,
        "near_examples": near_examples,
        "near_method": near_method,
        "summary": check_result("split_leakage", severity, finding),
    }
    emit_json(out)
    return exit_for_severity(out)

if __name__ == "__main__":
    raise SystemExit(main())
