#!/usr/bin/env python3
from qc_utils import *


def check_file(path: str, cfg: Dict[str, Any], sample_size: int) -> Dict[str, Any]:
    labels = Counter()
    norm_map: Dict[str, Counter[str]] = defaultdict(Counter)
    bad_labels = []
    declared = cfg.get("declared_labels")
    declared_set = {str(x) for x in declared} if declared else None
    total = 0
    for wrapped in iter_records(path, allow_json_errors=True):
        if detect_record_format(wrapped.record) != "classification" or not isinstance(wrapped.record, dict):
            continue
        total += 1
        label = stringify(wrapped.record.get("label"))
        labels[label] += 1
        norm_map[label.strip().lower()][label] += 1
        if declared_set is not None and label not in declared_set and len(bad_labels) < sample_size:
            bad_labels.append({"loc": wrapped.loc, "label": label, "sample": sanitize_sample(wrapped.record)})
    issues = []
    if declared_set is not None:
        unknown_count = sum(labels[l] for l in labels if l not in declared_set)
        if unknown_count:
            issues.append({"severity": "CRITICAL", "code": "label_not_in_declared_set", "message": f"{unknown_count} labels not in declared label set", "examples": bad_labels})
    normalization = []
    for norm, variants in norm_map.items():
        if len(variants) > 1:
            normalization.append({"normalized": norm, "variants": dict(variants)})
    if normalization:
        issues.append({"severity": "WARNING", "code": "label_normalization", "message": "Labels differ only by case/whitespace", "examples": normalization[:sample_size]})
    ratio = None
    if labels:
        mn, mx = min(labels.values()), max(labels.values())
        ratio = mx / max(1, mn)
        if ratio >= float(cfg.get("classification_majority_minority_warning_ratio", 10.0)):
            issues.append({"severity": "WARNING", "code": "class_imbalance", "message": f"Majority/minority ratio is {ratio:.2f}", "majority_minority_ratio": ratio})
    severity = "CRITICAL" if any(i["severity"] == "CRITICAL" for i in issues) else ("WARNING" if issues else "OK")
    finding = "Classification label issues found" if issues else "Classification label checks passed"
    return {"file": path, "record_count_checked": total, "severity": severity, "finding": finding, "label_counts": dict(labels), "majority_minority_ratio": ratio, "declared_labels": sorted(declared_set) if declared_set else None, "issues": issues}


def main() -> int:
    parser = common_parser("Check classification fine-tune label balance and normalization", multiple_inputs=True)
    args = parser.parse_args()
    cfg = load_config(args.config)
    sample_size = args.sample_size or cfg.get("sample_size", 5)
    files = []
    for inp in (args.input if isinstance(args.input, list) else [args.input]):
        files.extend(list_input_files(inp))
    results = [check_file(f, cfg, sample_size) for f in files]
    severity = "CRITICAL" if any(r["severity"] == "CRITICAL" for r in results) else ("WARNING" if any(r["severity"] == "WARNING" for r in results) else "OK")
    eprint(f"[{severity}] classification_check")
    out = {"script": "classification_check.py", "timestamp": now_iso(), "files": results, "summary": check_result("classification", severity, "Classification checks complete")}
    emit_json(out)
    return exit_for_severity(out)

if __name__ == "__main__":
    raise SystemExit(main())
