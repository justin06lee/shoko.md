#!/usr/bin/env python3
from qc_utils import *


def dedup_file(path: str, cfg: Dict[str, Any], sample_size: int) -> Dict[str, Any]:
    seen: Dict[str, Dict[str, Any]] = {}
    duplicate_count = 0
    examples: List[Dict[str, Any]] = []
    total = 0
    try:
        for wrapped in iter_records(path, allow_json_errors=True):
            total += 1
            if is_synthetic_record(wrapped.record):
                # Blank lines and unparseable rows are reported by validate_schema;
                # they all hash alike, so counting them here would be a false dup.
                continue
            h = record_hash(wrapped.record)
            if h in seen:
                duplicate_count += 1
                if len(examples) < sample_size:
                    examples.append({"hash": h, "first": seen[h], "duplicate": wrapped.loc, "sample": sanitize_sample(wrapped.record)})
            else:
                seen[h] = wrapped.loc
    except Exception as exc:
        return {"file": path, "record_count": total, "severity": "CRITICAL", "finding": str(exc), "error": str(exc)}
    severity = "WARNING" if duplicate_count else "OK"
    finding = f"{duplicate_count} exact duplicate record(s)" if duplicate_count else "No exact full-record duplicates"
    return {"file": path, "record_count": total, "unique_records": len(seen), "duplicate_count": duplicate_count, "duplicate_rate": (duplicate_count / total if total else 0), "severity": severity, "finding": finding, "examples": examples}


def main() -> int:
    parser = common_parser("Find exact full-record duplicates", multiple_inputs=True)
    args = parser.parse_args()
    cfg = load_config(args.config)
    sample_size = args.sample_size or cfg.get("sample_size", 5)
    files = []
    for inp in (args.input if isinstance(args.input, list) else [args.input]):
        files.extend(list_input_files(inp))
    results = [dedup_file(f, cfg, sample_size) for f in files]
    severity = "CRITICAL" if any(r["severity"] == "CRITICAL" for r in results) else ("WARNING" if any(r["severity"] == "WARNING" for r in results) else "OK")
    dupes = sum(r.get("duplicate_count", 0) for r in results)
    eprint(f"[{severity}] dedup_exact: {dupes} duplicate(s)")
    out = {"script": "dedup_exact.py", "timestamp": now_iso(), "files": results, "summary": check_result("exact_duplicates", severity, f"Found {dupes} exact duplicate record(s)")}
    emit_json(out)
    return exit_for_severity(out)

if __name__ == "__main__":
    raise SystemExit(main())
