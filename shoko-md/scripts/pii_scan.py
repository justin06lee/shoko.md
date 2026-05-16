#!/usr/bin/env python3
from qc_utils import *

PATTERNS = {
    "email": EMAIL_RE,
    "phone": PHONE_RE,
    "us_ssn": SSN_RE,
    "credit_card_candidate": CC_RE,
    "ipv4": IPV4_RE,
    "ipv6": IPV6_RE,
    "api_key": API_KEY_RE,
    "street_address": STREET_RE,
}


def matches_for(pattern_name: str, text: str) -> List[str]:
    vals = []
    rx = PATTERNS[pattern_name]
    for m in rx.finditer(text):
        val = m.group(0)
        if pattern_name == "credit_card_candidate" and not luhn_ok(val):
            continue
        if pattern_name == "phone":
            digits = re.sub(r"\D", "", val)
            if len(digits) < 7 or len(digits) > 15:
                continue
        vals.append(val)
    return vals


def scan_file(path: str, cfg: Dict[str, Any], sample_size: int) -> Dict[str, Any]:
    counts = Counter()
    samples: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    total = 0
    try:
        for wrapped in iter_records(path, allow_json_errors=True):
            total += 1
            bundle = record_text_bundle(wrapped.record)
            for name in PATTERNS:
                hits = matches_for(name, bundle)
                if hits:
                    counts[name] += len(hits)
                    if len(samples[name]) < sample_size:
                        samples[name].append({"loc": wrapped.loc, "sample": redact_text(bundle[:1000]), "match_count": len(hits)})
    except Exception as exc:
        return {"file": path, "severity": "CRITICAL", "finding": str(exc), "error": str(exc)}
    severity = "WARNING" if counts else "OK"
    finding = "Potential PII/secrets found by regex scan" if counts else "No regex PII/secrets matches found"
    return {"file": path, "record_count": total, "severity": severity, "finding": finding, "pattern_counts": dict(counts), "samples_redacted": dict(samples), "notes": ["Regex PII scanning is language- and pattern-biased, with US-heavy SSN/address coverage and possible false positives/negatives.", "ML-based PII detection is out of scope for this skill."]}


def main() -> int:
    parser = common_parser("Regex scan for PII, secrets, IPs, and loose addresses", multiple_inputs=True)
    args = parser.parse_args()
    cfg = load_config(args.config)
    sample_size = args.sample_size or cfg.get("pii_sample_size", cfg.get("sample_size", 5))
    files = []
    for inp in (args.input if isinstance(args.input, list) else [args.input]):
        files.extend(list_input_files(inp))
    results = [scan_file(f, cfg, sample_size) for f in files]
    severity = "CRITICAL" if any(r["severity"] == "CRITICAL" for r in results) else ("WARNING" if any(r["severity"] == "WARNING" for r in results) else "OK")
    total_hits = sum(sum(r.get("pattern_counts", {}).values()) for r in results)
    eprint(f"[{severity}] pii_scan: {total_hits} hit(s), redacted samples only")
    out = {"script": "pii_scan.py", "timestamp": now_iso(), "files": results, "summary": check_result("pii_scan", severity, f"Found {total_hits} regex PII/secret hit(s)")}
    emit_json(out)
    return exit_for_severity(out)

if __name__ == "__main__":
    raise SystemExit(main())
