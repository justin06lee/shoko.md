#!/usr/bin/env python3
from qc_utils import *


def issue(severity: str, code: str, message: str, loc: Dict[str, Any], sample: Any = None) -> Dict[str, Any]:
    out = {"severity": severity, "code": code, "message": message, "loc": loc}
    if sample is not None:
        out["sample"] = sanitize_sample(sample)
    return out


def validate_record(rec: Any, detected_format: str, wrapped: Record, cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []
    min_chars = int(cfg.get("min_trivial_chars", 3))
    if isinstance(rec, dict) and rec.get("__json_error__"):
        return [issue("CRITICAL", "invalid_json", rec.get("__json_error__", "Invalid JSON"), wrapped.loc, rec.get("__raw__"))]
    if not isinstance(rec, dict):
        if detected_format != "raw_text":
            issues.append(issue("CRITICAL", "record_not_object", "Record is not a JSON/object row", wrapped.loc, rec))
        return issues
    if rec.get("__empty_line__"):
        issues.append(issue("CRITICAL", "empty_line", "Empty line in JSONL dataset", wrapped.loc))
        return issues
    fmt = detected_format
    keys = set(rec.keys())
    if fmt == "openai_chat" or fmt == "anthropic_chat":
        msgs = extract_messages(rec)
        if not msgs:
            issues.append(issue("CRITICAL", "missing_messages", "Chat record missing non-empty messages/conversation list", wrapped.loc, rec))
        else:
            for i, msg in enumerate(msgs):
                role = message_role(msg)
                content = message_content(msg)
                if not role:
                    issues.append(issue("CRITICAL", "missing_role", f"messages[{i}] missing role/speaker", wrapped.loc, msg))
                if content is None or not isinstance(content, str):
                    issues.append(issue("CRITICAL", "bad_content_type", f"messages[{i}].content is not a string-like value", wrapped.loc, msg))
    elif fmt == "preference_pair":
        prompt = rec.get("prompt", rec.get("input", rec.get("question")))
        if prompt is None:
            issues.append(issue("CRITICAL", "missing_prompt", "Preference pair missing prompt/input/question", wrapped.loc, rec))
        for fld in ["chosen", "rejected"]:
            if fld not in rec or rec.get(fld) is None:
                issues.append(issue("CRITICAL", f"missing_{fld}", f"Preference pair missing {fld}", wrapped.loc, rec))
            elif not isinstance(rec.get(fld), (str, dict, list)):
                issues.append(issue("CRITICAL", f"bad_{fld}_type", f"{fld} has unsupported type", wrapped.loc, rec))
    elif fmt == "prompt_completion":
        if not (("prompt" in keys and "completion" in keys) or ("input" in keys and "output" in keys) or ("instruction" in keys and "response" in keys) or ("question" in keys and "answer" in keys)):
            issues.append(issue("CRITICAL", "missing_prompt_completion", "Missing prompt/completion, input/output, instruction/response, or question/answer pair", wrapped.loc, rec))
    elif fmt == "classification":
        for fld in ["text", "label"]:
            if fld not in rec or rec.get(fld) is None:
                issues.append(issue("CRITICAL", f"missing_{fld}", f"Classification row missing {fld}", wrapped.loc, rec))
    elif fmt == "raw_text":
        if "text" not in rec:
            issues.append(issue("CRITICAL", "missing_text", "Raw text row missing text field", wrapped.loc, rec))
    elif fmt in {"mixed", "invalid", "empty", "unknown", "unreadable", "too_large"}:
        return issues

    for fld, val in text_fields(rec).items():
        if val is None:
            issues.append(issue("CRITICAL", "null_text", f"{fld} is null", wrapped.loc, rec))
            continue
        if not isinstance(val, str):
            issues.append(issue("CRITICAL", "bad_text_type", f"{fld} is not a string", wrapped.loc, rec))
            continue
        stripped = val.strip()
        if stripped == "":
            issues.append(issue("WARNING", "empty_text", f"{fld} is empty or whitespace-only", wrapped.loc, rec))
        elif len(stripped) < min_chars:
            issues.append(issue("WARNING", "trivial_text", f"{fld} is under {min_chars} characters", wrapped.loc, rec))
        if stripped.lower() == fld.lower():
            issues.append(issue("WARNING", "fieldname_as_value", f"{fld} is identical to the field name", wrapped.loc, rec))
        for tok in SPECIAL_TOKEN_PATTERNS:
            if tok in val:
                issues.append(issue("WARNING", "special_token", f"{fld} contains special token {tok}", wrapped.loc, rec))
                break
        if "\x00" in val:
            issues.append(issue("CRITICAL", "null_byte_in_text", f"{fld} contains NULL byte", wrapped.loc, rec))
    return issues


def validate_file(path: str, cfg: Dict[str, Any], sample_size: int) -> Dict[str, Any]:
    fmt_info = detect_file_format(path)
    fmt = fmt_info.get("format")
    issues: List[Dict[str, Any]] = []
    issue_counts: Counter[str] = Counter()
    record_count = 0
    if fmt_info.get("issues"):
        issues.extend(fmt_info["issues"][:sample_size])
        for it in fmt_info["issues"]:
            issue_counts[it.get("message", "format_issue")] += 1
    if fmt in {"mixed", "invalid", "empty", "unreadable", "too_large"}:
        severity = "CRITICAL"
        return {"file": path, "detected_format": fmt, "record_count": fmt_info.get("record_count_sampled", 0), "severity": severity, "finding": f"Cannot fully validate schema because format is {fmt}", "issues": issues, "issue_counts": dict(issue_counts)}
    try:
        for wrapped in iter_records(path, allow_json_errors=True):
            record_count += 1
            for it in validate_record(wrapped.record, fmt, wrapped, cfg):
                issue_counts[it["code"]] += 1
                if len(issues) < sample_size * 10:
                    issues.append(it)
    except Exception as exc:
        issues.append(issue("CRITICAL", "read_error", str(exc), {"file": path}, None))
        issue_counts["read_error"] += 1
    severity = "CRITICAL" if any(i.get("severity") == "CRITICAL" for i in issues) else ("WARNING" if issues else "OK")
    if record_count == 0:
        severity = "CRITICAL"
        issues.append({"severity": "CRITICAL", "code": "empty_file", "message": "File contains 0 records", "loc": {"file": path}})
    finding = "Schema/content issues found" if issues else "Schema validation passed"
    return {"file": path, "detected_format": fmt, "record_count": record_count, "severity": severity, "finding": finding, "issues": issues, "issue_counts": dict(issue_counts)}


def main() -> int:
    parser = common_parser("Validate fine-tuning dataset schema and empty/trivial content", multiple_inputs=True)
    args = parser.parse_args()
    cfg = load_config(args.config)
    sample_size = args.sample_size or cfg.get("sample_size", 5)
    files = []
    for inp in (args.input if isinstance(args.input, list) else [args.input]):
        files.extend(list_input_files(inp))
    results = [validate_file(f, cfg, sample_size) for f in files]
    severity = "CRITICAL" if any(r["severity"] == "CRITICAL" for r in results) else ("WARNING" if any(r["severity"] == "WARNING" for r in results) else "OK")
    total = sum(r.get("record_count", 0) for r in results)
    eprint(f"[{severity}] validate_schema: {total} record(s), {len(results)} file(s)")
    out = {"script": "validate_schema.py", "timestamp": now_iso(), "files": results, "summary": check_result("schema_validation", severity, f"Validated {total} record(s) across {len(results)} file(s)")}
    emit_json(out)
    return exit_for_severity(out)

if __name__ == "__main__":
    raise SystemExit(main())
