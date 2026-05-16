#!/usr/bin/env python3
from qc_utils import *


def main() -> int:
    parser = common_parser("Detect fine-tuning dataset format", multiple_inputs=True)
    parser.add_argument("--sniff-records", type=int, default=2000, help="Records to sniff per file")
    args = parser.parse_args()
    cfg = load_config(args.config)
    sample_size = args.sample_size or cfg.get("sample_size", 5)
    inputs = args.input if isinstance(args.input, list) else [args.input]
    files = []
    for inp in inputs:
        files.extend(list_input_files(inp))
    results = []
    for f in files:
        err = check_file_size(Path(f), cfg)
        if err:
            results.append({"file": f, "format": "too_large", "critical": True, "issues": [{"severity": "CRITICAL", "message": err}]})
            continue
        res = detect_file_format(f, sample_size=args.sniff_records)
        results.append(res)
        sev = "CRITICAL" if res.get("critical") else "OK"
        eprint(f"[{sev}] {f}: {res.get('format')} counts={res.get('format_counts')}")
    out = {
        "script": "detect_format.py",
        "timestamp": now_iso(),
        "files": results,
        "summary": check_result("format_detection", "CRITICAL" if any(r.get("critical") for r in results) else "OK", f"Detected formats for {len(results)} file(s)"),
    }
    emit_json(out)
    return exit_for_severity(out)

if __name__ == "__main__":
    raise SystemExit(main())
