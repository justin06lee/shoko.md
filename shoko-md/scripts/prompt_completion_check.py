#!/usr/bin/env python3
from qc_utils import *


def pair_fields(rec: Dict[str, Any]) -> Tuple[str, str, str, str]:
    pairs = [("prompt", "completion"), ("input", "output"), ("instruction", "response"), ("question", "answer")]
    for a, b in pairs:
        if a in rec and b in rec:
            return a, stringify(rec.get(a)), b, stringify(rec.get(b))
    return "input", stringify(primary_input_text(rec)), "output", ""


def check_file(path: str, cfg: Dict[str, Any], sample_size: int) -> Dict[str, Any]:
    issues = []
    counts = Counter()
    total = 0
    for wrapped in iter_records(path, allow_json_errors=True):
        if detect_record_format(wrapped.record) != "prompt_completion" or not isinstance(wrapped.record, dict):
            continue
        total += 1
        in_name, inp, out_name, out = pair_fields(wrapped.record)
        if not out.strip():
            counts["empty_completion"] += 1
            if len(issues) < sample_size:
                issues.append({"severity": "CRITICAL", "code": "empty_completion", "message": f"{out_name} is empty", "loc": wrapped.loc, "sample": sanitize_sample(wrapped.record)})
        if inp.strip() and normalize_space(inp) == normalize_space(out):
            counts["completion_copies_prompt"] += 1
            if len(issues) < sample_size:
                issues.append({"severity": "WARNING", "code": "completion_copies_prompt", "message": f"{out_name} appears to copy {in_name}", "loc": wrapped.loc, "sample": sanitize_sample(wrapped.record)})
    severity = "CRITICAL" if any(i["severity"] == "CRITICAL" for i in issues) else ("WARNING" if issues else "OK")
    finding = "Prompt-completion issues found" if issues else "Prompt-completion deterministic checks passed"
    return {"file": path, "record_count_checked": total, "severity": severity, "finding": finding, "issue_counts": dict(counts), "issues": issues, "scope_note": "Prompt-completion semantic alignment is out of scope; this skill does not fake an LLM-as-judge alignment score."}


def main() -> int:
    parser = common_parser("Check prompt-completion records", multiple_inputs=True)
    args = parser.parse_args()
    cfg = load_config(args.config)
    sample_size = args.sample_size or cfg.get("sample_size", 5)
    files = []
    for inp in (args.input if isinstance(args.input, list) else [args.input]):
        files.extend(list_input_files(inp))
    results = [check_file(f, cfg, sample_size) for f in files]
    severity = "CRITICAL" if any(r["severity"] == "CRITICAL" for r in results) else ("WARNING" if any(r["severity"] == "WARNING" for r in results) else "OK")
    eprint(f"[{severity}] prompt_completion_check")
    out = {"script": "prompt_completion_check.py", "timestamp": now_iso(), "files": results, "summary": check_result("prompt_completion", severity, "Prompt-completion checks complete")}
    emit_json(out)
    return exit_for_severity(out)

if __name__ == "__main__":
    raise SystemExit(main())
