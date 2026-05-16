#!/usr/bin/env python3
from qc_utils import *


def scan_file(path: str, cfg: Dict[str, Any], sample_size: int) -> Dict[str, Any]:
    p = Path(path)
    issues = []
    counts = Counter()
    samples = defaultdict(list)
    try:
        data = p.read_bytes()
    except Exception as exc:
        return {"file": path, "severity": "CRITICAL", "finding": str(exc), "issues": [{"severity": "CRITICAL", "message": str(exc)}]}
    if b"\x00" in data:
        counts["null_bytes"] += data.count(b"\x00")
        issues.append({"severity": "CRITICAL", "pattern": "NULL byte", "count": counts["null_bytes"], "message": "NULL bytes present"})
    if data.startswith(b"\xef\xbb\xbf"):
        counts["bom_at_start"] += 1
        issues.append({"severity": "WARNING", "pattern": "BOM", "count": 1, "message": "UTF-8 BOM at start of file"})
    stray_bom = data.count(b"\xef\xbb\xbf") - (1 if data.startswith(b"\xef\xbb\xbf") else 0)
    if stray_bom:
        counts["stray_bom"] += stray_bom
        issues.append({"severity": "WARNING", "pattern": "stray BOM", "count": stray_bom, "message": "BOM occurs after the start of the file"})
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        prefix = data[max(0, exc.start-40):exc.end+40]
        issues.append({"severity": "CRITICAL", "pattern": "invalid_utf8", "message": str(exc), "sample_bytes_hex": prefix.hex()})
        text = data.decode("utf-8", errors="replace")
    for pat in MOJIBAKE_PATTERNS:
        c = text.count(pat)
        if c:
            counts[f"mojibake:{pat}"] = c
            idx = text.find(pat)
            excerpt = text[max(0, idx-80):idx+120]
            samples[f"mojibake:{pat}"].append(redact_text(excerpt))
    for key, count in counts.items():
        if key.startswith("mojibake:"):
            pat = key.split(":", 1)[1]
            issues.append({"severity": "WARNING", "pattern": pat, "count": count, "samples": samples[key][:sample_size], "message": "Possible mojibake / broken text encoding"})
    severity = "CRITICAL" if any(i["severity"] == "CRITICAL" for i in issues) else ("WARNING" if issues else "OK")
    finding = "Encoding issues found" if issues else "UTF-8/encoding sanity checks passed"
    return {"file": path, "severity": severity, "finding": finding, "issues": issues, "counts": dict(counts), "bytes": len(data)}


def main() -> int:
    parser = common_parser("Check UTF-8, BOMs, NULL bytes, and mojibake", multiple_inputs=True)
    args = parser.parse_args()
    cfg = load_config(args.config)
    sample_size = args.sample_size or cfg.get("sample_size", 5)
    files = []
    for inp in (args.input if isinstance(args.input, list) else [args.input]):
        files.extend(list_input_files(inp))
    results = [scan_file(f, cfg, sample_size) for f in files]
    severity = "CRITICAL" if any(r["severity"] == "CRITICAL" for r in results) else ("WARNING" if any(r["severity"] == "WARNING" for r in results) else "OK")
    eprint(f"[{severity}] encoding_check: {len(results)} file(s)")
    out = {"script": "encoding_check.py", "timestamp": now_iso(), "files": results, "summary": check_result("encoding_sanity", severity, "Encoding sanity checks complete")}
    emit_json(out)
    return exit_for_severity(out)

if __name__ == "__main__":
    raise SystemExit(main())
