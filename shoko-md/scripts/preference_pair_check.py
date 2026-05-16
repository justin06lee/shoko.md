#!/usr/bin/env python3
from qc_utils import *


def prompt_text(rec: Dict[str, Any]) -> str:
    return stringify(rec.get("prompt", rec.get("input", rec.get("question", ""))))


def check_file(path: str, cfg: Dict[str, Any], sample_size: int) -> Dict[str, Any]:
    total = 0
    issues = []
    counts = Counter()
    prompt_pairs: Dict[str, Tuple[str, str, Dict[str, Any]]] = {}
    chosen_lens: List[int] = []
    rejected_lens: List[int] = []
    manual_samples = []
    for wrapped in iter_records(path, allow_json_errors=True):
        if detect_record_format(wrapped.record) != "preference_pair" or not isinstance(wrapped.record, dict):
            continue
        total += 1
        rec = wrapped.record
        p = prompt_text(rec)
        chosen = stringify(rec.get("chosen"))
        rejected = stringify(rec.get("rejected"))
        chosen_lens.append(len(chosen))
        rejected_lens.append(len(rejected))
        if chosen == rejected:
            counts["chosen_equals_rejected"] += 1
            if len(issues) < sample_size:
                issues.append({"severity": "CRITICAL", "code": "chosen_equals_rejected", "message": "chosen and rejected are identical", "loc": wrapped.loc, "sample": sanitize_sample(rec)})
        ph = text_hash(normalize_space(p).lower())
        pair = (text_hash(normalize_space(chosen).lower()), text_hash(normalize_space(rejected).lower()))
        if ph in prompt_pairs:
            prev_ch, prev_rej, prev_loc = prompt_pairs[ph]
            if pair != (prev_ch, prev_rej):
                counts["conflicting_prompt_pairs"] += 1
                if len(issues) < sample_size:
                    issues.append({"severity": "WARNING", "code": "conflicting_prompt_pairs", "message": "Same prompt has conflicting chosen/rejected across rows", "loc": wrapped.loc, "previous_loc": prev_loc})
        else:
            prompt_pairs[ph] = (pair[0], pair[1], wrapped.loc)
        if len(manual_samples) < sample_size:
            manual_samples.append({"loc": wrapped.loc, "prompt_excerpt": redact_text(p[:250]), "chosen_excerpt": redact_text(chosen[:250]), "rejected_excerpt": redact_text(rejected[:250]), "note": "Heuristic only: manually verify chosen is genuinely better than rejected; this skill does not use an LLM judge."})
    mean_chosen = statistics.mean(chosen_lens) if chosen_lens else 0
    mean_rejected = statistics.mean(rejected_lens) if rejected_lens else 0
    length_delta = mean_chosen - mean_rejected
    denom = max(1.0, mean_rejected)
    bias_ratio = length_delta / denom
    if total and bias_ratio > float(cfg.get("preference_length_bias_warning_ratio", 0.35)):
        counts["chosen_much_longer"] += 1
        issues.append({"severity": "WARNING", "code": "chosen_much_longer", "message": f"Mean chosen length is {bias_ratio:.1%} longer than mean rejected length; possible length-bias signal", "mean_chosen_chars": mean_chosen, "mean_rejected_chars": mean_rejected})
    severity = "CRITICAL" if any(i["severity"] == "CRITICAL" for i in issues) else ("WARNING" if issues else "OK")
    finding = "Preference-pair issues found" if issues else "Preference-pair deterministic checks passed"
    return {"file": path, "record_count_checked": total, "severity": severity, "finding": finding, "issue_counts": dict(counts), "issues": issues[:sample_size*2], "length_bias": {"mean_chosen_chars": mean_chosen, "mean_rejected_chars": mean_rejected, "mean_delta_chars": length_delta, "ratio_vs_rejected": bias_ratio}, "manual_swap_review_samples": manual_samples}


def main() -> int:
    parser = common_parser("Check DPO/RLHF preference-pair data", multiple_inputs=True)
    args = parser.parse_args()
    cfg = load_config(args.config)
    sample_size = args.sample_size or cfg.get("sample_size", 5)
    files = []
    for inp in (args.input if isinstance(args.input, list) else [args.input]):
        files.extend(list_input_files(inp))
    results = [check_file(f, cfg, sample_size) for f in files]
    severity = "CRITICAL" if any(r["severity"] == "CRITICAL" for r in results) else ("WARNING" if any(r["severity"] == "WARNING" for r in results) else "OK")
    eprint(f"[{severity}] preference_pair_check")
    out = {"script": "preference_pair_check.py", "timestamp": now_iso(), "files": results, "summary": check_result("preference_pairs", severity, "Preference pair checks complete")}
    emit_json(out)
    return exit_for_severity(out)

if __name__ == "__main__":
    raise SystemExit(main())
