#!/usr/bin/env python3
from qc_utils import *


def check_file(path: str, cfg: Dict[str, Any], sample_size: int) -> Dict[str, Any]:
    issues = []
    counts = Counter()
    system_prompts = Counter()
    total = 0
    for wrapped in iter_records(path, allow_json_errors=True):
        fmt = detect_record_format(wrapped.record)
        if fmt not in {"openai_chat", "anthropic_chat"}:
            continue
        total += 1
        msgs = extract_messages(wrapped.record)
        roles = [message_role(m) for m in msgs]
        if roles and "system" in roles[1:]:
            counts["system_not_at_start"] += 1
            if len(issues) < sample_size:
                issues.append({"severity": "CRITICAL", "code": "system_not_at_start", "message": "System message appears after first turn", "loc": wrapped.loc, "roles": roles})
        non_tool = [r for r in roles if r not in {"system", "tool"}]
        for a, b in zip(non_tool, non_tool[1:]):
            if a == b and a in {"user", "assistant"}:
                counts[f"same_role_consecutive_{a}"] += 1
                if len(issues) < sample_size:
                    issues.append({"severity": "CRITICAL", "code": "role_alternation", "message": f"Two {a} turns in a row", "loc": wrapped.loc, "roles": roles})
                break
        if roles and roles[-1] != "assistant":
            counts["does_not_end_assistant"] += 1
            if len(issues) < sample_size:
                issues.append({"severity": "WARNING", "code": "does_not_end_assistant", "message": "Conversation does not end on assistant", "loc": wrapped.loc, "roles": roles})
        for i, m in enumerate(msgs):
            role = message_role(m)
            content = message_content(m)
            if role == "assistant" and not content.strip() and not m.get("tool_calls") and not m.get("function_call"):
                counts["empty_assistant_turn"] += 1
                if len(issues) < sample_size:
                    issues.append({"severity": "CRITICAL", "code": "empty_assistant_turn", "message": f"Empty assistant turn at messages[{i}]", "loc": wrapped.loc})
            if m.get("tool_calls") is not None:
                if not isinstance(m.get("tool_calls"), list):
                    counts["bad_tool_calls_type"] += 1
                    issues.append({"severity": "CRITICAL", "code": "bad_tool_calls_type", "message": "tool_calls must be a list", "loc": wrapped.loc})
                else:
                    for tc in m.get("tool_calls", []):
                        if not isinstance(tc, dict) or not (tc.get("id") and tc.get("type")):
                            counts["bad_tool_call_object"] += 1
                            issues.append({"severity": "WARNING", "code": "bad_tool_call_object", "message": "tool_call object missing id/type", "loc": wrapped.loc})
            if role == "tool" and not (m.get("tool_call_id") or m.get("name")):
                counts["bad_tool_response"] += 1
                issues.append({"severity": "WARNING", "code": "bad_tool_response", "message": "Tool/function response missing tool_call_id or name", "loc": wrapped.loc})
        if msgs and message_role(msgs[0]) == "system":
            system_prompts[message_content(msgs[0]).strip()] += 1
        else:
            system_prompts[""] += 1
    severity = "CRITICAL" if any(i["severity"] == "CRITICAL" for i in issues) else ("WARNING" if issues else "OK")
    finding = "Chat format issues found" if issues else "Chat role and tool/function format checks passed"
    return {"file": path, "record_count_checked": total, "severity": severity, "finding": finding, "issue_counts": dict(counts), "issues": issues[:sample_size*2], "unique_system_prompt_count": len(system_prompts), "system_prompt_top": [{"count": c, "excerpt": redact_text(s[:300])} for s, c in system_prompts.most_common(sample_size)]}


def main() -> int:
    parser = common_parser("Check chat dataset role alternation and tool/function call shape", multiple_inputs=True)
    args = parser.parse_args()
    cfg = load_config(args.config)
    sample_size = args.sample_size or cfg.get("sample_size", 5)
    files = []
    for inp in (args.input if isinstance(args.input, list) else [args.input]):
        files.extend(list_input_files(inp))
    results = [check_file(f, cfg, sample_size) for f in files]
    severity = "CRITICAL" if any(r["severity"] == "CRITICAL" for r in results) else ("WARNING" if any(r["severity"] == "WARNING" for r in results) else "OK")
    eprint(f"[{severity}] chat_format_check")
    out = {"script": "chat_format_check.py", "timestamp": now_iso(), "files": results, "summary": check_result("chat_format", severity, "Chat format checks complete")}
    emit_json(out)
    return exit_for_severity(out)

if __name__ == "__main__":
    raise SystemExit(main())
