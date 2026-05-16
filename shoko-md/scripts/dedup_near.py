#!/usr/bin/env python3
from qc_utils import *


def union_find(n: int):
    parent = list(range(n))
    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra
    return parent, find, union


def datasketch_clusters(records: List[Tuple[Dict[str, Any], str]], threshold: float, num_perm: int) -> Tuple[List[List[int]], str]:
    from datasketch import MinHash, MinHashLSH  # type: ignore
    lsh = MinHashLSH(threshold=threshold, num_perm=num_perm)
    minhashes = []
    for i, (_loc, text) in enumerate(records):
        mh = MinHash(num_perm=num_perm)
        shingles = token_shingles(text)
        if not shingles:
            shingles = {""}
        for sh in shingles:
            mh.update(sh.encode("utf-8", errors="replace"))
        key = str(i)
        lsh.insert(key, mh)
        minhashes.append(mh)
    parent, find, union = union_find(len(records))
    for i, mh in enumerate(minhashes):
        for key in lsh.query(mh):
            j = int(key)
            if i != j:
                union(i, j)
    groups: Dict[int, List[int]] = defaultdict(list)
    for i in range(len(records)):
        groups[find(i)].append(i)
    return [g for g in groups.values() if len(g) > 1], "datasketch_minhash_lsh"


def fallback_clusters(records: List[Tuple[Dict[str, Any], str]], threshold: float, max_records: int) -> Tuple[List[List[int]], str]:
    if len(records) > max_records:
        raise RuntimeError(f"datasketch is not installed and fallback pairwise Jaccard is limited to {max_records} records")
    shingled = [token_shingles(t) for _loc, t in records]
    parent, find, union = union_find(len(records))
    for i in range(len(records)):
        for j in range(i + 1, len(records)):
            if jaccard(shingled[i], shingled[j]) >= threshold:
                union(i, j)
    groups: Dict[int, List[int]] = defaultdict(list)
    for i in range(len(records)):
        groups[find(i)].append(i)
    return [g for g in groups.values() if len(g) > 1], "fallback_pairwise_jaccard_no_datasketch"


def near_file(path: str, cfg: Dict[str, Any], sample_size: int) -> Dict[str, Any]:
    threshold = float(cfg.get("near_duplicate_threshold", 0.85))
    max_records = int(cfg.get("near_duplicate_max_records", 250000))
    fallback_max = int(cfg.get("near_duplicate_fallback_max_records", 5000))
    records: List[Tuple[Dict[str, Any], str]] = []
    total = 0
    for wrapped in iter_records(path, allow_json_errors=True):
        total += 1
        if len(records) < max_records:
            records.append((wrapped.loc, primary_input_text(wrapped.record)))
    if total > max_records:
        return {"file": path, "record_count": total, "severity": "WARNING", "finding": f"Skipped near-duplicate check beyond configured max {max_records}; raise near_duplicate_max_records if memory allows", "clusters": [], "cluster_count": 0, "method": "skipped_too_many_records"}
    try:
        clusters, method = datasketch_clusters(records, threshold, int(cfg.get("near_duplicate_num_perm", 128)))
    except Exception as exc:
        try:
            clusters, method = fallback_clusters(records, threshold, fallback_max)
        except Exception as exc2:
            return {"file": path, "record_count": total, "severity": "WARNING", "finding": f"Near-duplicate check unavailable: {exc2}", "dependency_error": str(exc), "clusters": [], "cluster_count": 0, "method": "unavailable"}
    cluster_summaries = []
    clustered_records = set()
    for group in clusters:
        clustered_records.update(group)
    for group in sorted(clusters, key=len, reverse=True)[:sample_size]:
        members = [{"loc": records[i][0], "input_excerpt": redact_text(records[i][1][:300])} for i in group[:sample_size]]
        cluster_summaries.append({"size": len(group), "members": members})
    severity = "WARNING" if clusters else "OK"
    finding = f"{len(clusters)} near-duplicate cluster(s) at threshold {threshold}" if clusters else "No near-duplicate prompt/input clusters found"
    return {"file": path, "record_count": total, "severity": severity, "finding": finding, "threshold": threshold, "method": method, "cluster_count": len(clusters), "records_in_clusters": len(clustered_records), "clusters": cluster_summaries}


def main() -> int:
    parser = common_parser("Find near-duplicates using MinHash LSH on prompt/input text", multiple_inputs=True)
    parser.add_argument("--threshold", type=float, default=None)
    args = parser.parse_args()
    cfg = load_config(args.config)
    if args.threshold is not None:
        cfg["near_duplicate_threshold"] = args.threshold
    sample_size = args.sample_size or cfg.get("sample_size", 5)
    files = []
    for inp in (args.input if isinstance(args.input, list) else [args.input]):
        files.extend(list_input_files(inp))
    results = [near_file(f, cfg, sample_size) for f in files]
    severity = "CRITICAL" if any(r["severity"] == "CRITICAL" for r in results) else ("WARNING" if any(r["severity"] == "WARNING" for r in results) else "OK")
    clusters = sum(r.get("cluster_count", 0) for r in results)
    eprint(f"[{severity}] dedup_near: {clusters} cluster(s)")
    out = {"script": "dedup_near.py", "timestamp": now_iso(), "files": results, "summary": check_result("near_duplicates", severity, f"Found {clusters} near-duplicate cluster(s)")}
    emit_json(out)
    return exit_for_severity(out)

if __name__ == "__main__":
    raise SystemExit(main())
