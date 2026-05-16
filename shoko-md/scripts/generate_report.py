#!/usr/bin/env python3
from qc_utils import *


def load_json_file(path: Path) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"script": path.name, "summary": check_result(path.stem, "WARNING", f"Could not read JSON result: {exc}")}


def load_results(paths: List[str]) -> List[Dict[str, Any]]:
    files: List[Path] = []
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            files.extend(sorted(x for x in p.glob("*.json") if x.name != "final_report.json"))
        else:
            files.append(p)
    return [r for f in files if (r := load_json_file(f)) is not None and isinstance(r, dict) and ("script" in r or "summary" in r)]


def summary_from_result(res: Dict[str, Any]) -> Dict[str, str]:
    summary = res.get("summary") or {}
    check = summary.get("check") or Path(str(res.get("script", "unknown"))).stem
    severity = summary.get("severity", "INFO")
    finding = summary.get("finding", "")
    return {"check": str(check), "severity": str(severity), "finding": str(finding)}


def collect_detected_formats(results: List[Dict[str, Any]]) -> Dict[str, str]:
    out = {}
    for r in results:
        if r.get("script") == "detect_format.py":
            for f in r.get("files", []):
                out[f.get("file", "")] = f.get("format", "unknown")
    return out


def collect_record_counts(results: List[Dict[str, Any]]) -> Dict[str, int]:
    counts = {}
    for r in results:
        if r.get("script") == "validate_schema.py":
            for f in r.get("files", []):
                counts[f.get("file", "")] = int(f.get("record_count", 0) or 0)
    return counts


def md_table(rows: List[List[str]], headers: List[str]) -> str:
    def esc(x: Any) -> str:
        return str(x).replace("|", "\\|").replace("\n", " ")
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(esc(x) for x in row) + " |")
    return "\n".join(lines)


def section_for_issues(title: str, results: List[Dict[str, Any]], desired: str) -> str:
    lines = [f"## {title}", ""]
    found = False
    for r in results:
        script = r.get("script", "unknown")
        # Generic nested traversal, but summarize only direct file/result issue arrays.
        direct = []
        for f in r.get("files", []) if isinstance(r.get("files"), list) else []:
            if not isinstance(f, dict):
                continue
            for it in f.get("issues", []) or []:
                if it.get("severity") == desired:
                    direct.append((f.get("file"), it))
            # Some outputs store examples without issues but severity summary.
            if desired == "WARNING" and f.get("severity") == "WARNING" and not f.get("issues"):
                direct.append((f.get("file"), {"message": f.get("finding", "Warning"), "examples": f.get("examples") or f.get("clusters") or f.get("samples_redacted")}))
        if r.get("summary", {}).get("severity") == desired and not direct:
            direct.append((", ".join(r.get("files", [])) if isinstance(r.get("files"), list) else "", {"message": r.get("summary", {}).get("finding", "Issue")}))
        if direct:
            found = True
            lines.append(f"### {Path(str(script)).stem}")
            for file_name, it in direct[:10]:
                msg = it.get("message") or it.get("finding") or json.dumps(it, ensure_ascii=False)[:200]
                loc = it.get("loc")
                loc_s = f" at `{loc}`" if loc else ""
                file_s = f" in `{file_name}`" if file_name else ""
                lines.append(f"- **{it.get('code', 'issue')}**{file_s}{loc_s}: {msg}")
                for key in ["examples", "sample", "samples", "members"]:
                    if key in it and it[key]:
                        lines.append("  - Example: `" + redact_text(bounded_repr(it[key], 700)).replace("`", "'") + "`")
                        break
            lines.append("")
    if not found:
        lines.append(f"No {desired.lower()} issues reported.")
        lines.append("")
    return "\n".join(lines)


def stats_appendix(results: List[Dict[str, Any]]) -> str:
    lines = ["## Stats appendix", ""]
    for r in results:
        script = r.get("script")
        if script == "length_stats.py":
            lines.append("### Length distributions")
            for f in r.get("files", []):
                lines.append(f"**{f.get('file')}**")
                tok = f.get("token_stats", {})
                chars = f.get("char_stats", {})
                lines.append(f"- Tokenizer: `{f.get('tokenizer')}`" + (" (approximate)" if f.get("token_counts_are_approximate") else ""))
                lines.append(f"- Tokens: p50={tok.get('p50')}, p90={tok.get('p90')}, p99={tok.get('p99')}, max={tok.get('max')}")
                lines.append(f"- Characters: p50={chars.get('p50')}, p90={chars.get('p90')}, p99={chars.get('p99')}, max={chars.get('max')}")
                if f.get("context_window_exceed_counts"):
                    lines.append(f"- Context-window exceed counts: `{f.get('context_window_exceed_counts')}`")
                hist = f.get("token_histogram") or []
                if hist:
                    lines.append("```text")
                    lines.extend(hist[:12])
                    lines.append("```")
                lines.append("")
        elif script == "classification_check.py":
            lines.append("### Classification label balance")
            for f in r.get("files", []):
                if f.get("label_counts"):
                    rows = [[k, str(v)] for k, v in sorted(f.get("label_counts", {}).items(), key=lambda kv: str(kv[0]))]
                    lines.append(f"**{f.get('file')}**")
                    lines.append(md_table(rows, ["Label", "Count"]))
                    lines.append(f"Majority/minority ratio: `{f.get('majority_minority_ratio')}`")
                    lines.append("")
        elif script == "chat_format_check.py":
            lines.append("### Chat system prompt consistency")
            for f in r.get("files", []):
                if f.get("record_count_checked"):
                    lines.append(f"**{f.get('file')}**: {f.get('unique_system_prompt_count')} unique system prompt(s).")
                    for sp in f.get("system_prompt_top", [])[:5]:
                        lines.append(f"- {sp.get('count')} row(s): `{sp.get('excerpt')}`")
                    lines.append("")
        elif script == "pii_scan.py":
            lines.append("### PII/secrets regex counts")
            for f in r.get("files", []):
                if f.get("pattern_counts"):
                    rows = [[k, str(v)] for k, v in sorted(f.get("pattern_counts", {}).items())]
                    lines.append(f"**{f.get('file')}**")
                    lines.append(md_table(rows, ["Pattern", "Count"]))
                    lines.append("Samples in this report are redacted. Regex coverage is language- and US-biased; higher-recall PII review needs a dedicated PII tool.")
                    lines.append("")
        elif script == "split_leakage.py":
            lines.append("### Split leakage")
            lines.append(f"Split counts: `{r.get('split_counts')}`")
            lines.append(f"Exact leakage count: `{r.get('exact_leakage_count')}`")
            lines.append(f"Near leakage clusters: `{r.get('near_leakage_cluster_count')}` using `{r.get('near_method')}`")
            if r.get("exact_examples"):
                lines.append("Exact leakage examples: `" + bounded_repr(r.get("exact_examples"), 1000).replace("`", "'") + "`")
            if r.get("near_examples"):
                lines.append("Near leakage examples: `" + bounded_repr(r.get("near_examples"), 1000).replace("`", "'") + "`")
            lines.append("")
    if len(lines) == 2:
        lines.append("No statistical appendices available.")
    return "\n".join(lines)


def suggested_actions(results: List[Dict[str, Any]]) -> str:
    rows = [summary_from_result(r) for r in results]
    critical = [r for r in rows if r["severity"] == "CRITICAL"]
    warnings = [r for r in rows if r["severity"] == "WARNING"]
    lines = ["## Suggested next actions", ""]
    n = 1
    for r in critical:
        lines.append(f"{n}. Fix **{r['check']}** first: {r['finding']}")
        n += 1
    cheap_order = ["schema_validation", "format_detection", "split_leakage", "pii_scan", "exact_duplicates", "chat_format", "preference_pairs", "classification", "prompt_completion", "near_duplicates", "length_distribution", "encoding_sanity"]
    warnings = sorted(warnings, key=lambda r: cheap_order.index(r["check"]) if r["check"] in cheap_order else 999)
    for r in warnings:
        lines.append(f"{n}. Then address **{r['check']}**: {r['finding']}")
        n += 1
    lines.append(f"{n}. Manually inspect 20-50 random records before training; deterministic QC catches structural bugs, not response quality or factual correctness.")
    return "\n".join(lines)


def write_report(results: List[Dict[str, Any]], output: Optional[str] = None) -> str:
    formats = collect_detected_formats(results)
    counts = collect_record_counts(results)
    all_files = sorted(set(formats) | set(counts))
    header_rows = [[f, str(counts.get(f, "unknown")), formats.get(f, "unknown")] for f in all_files]
    summary_rows = [[s["check"], s["severity"], s["finding"]] for s in [summary_from_result(r) for r in results]]
    lines = [
        "# Fine-tuning dataset QC report",
        "",
        f"Generated: {now_iso()}",
        "",
        "## Header",
        "",
        md_table(header_rows or [["unknown", "unknown", "unknown"]], ["File", "Record count", "Detected format"]),
        "",
        "## Summary table",
        "",
        md_table(summary_rows, ["Check", "Severity", "Finding"]),
        "",
        section_for_issues("Critical issues", results, "CRITICAL"),
        section_for_issues("Warnings", results, "WARNING"),
        stats_appendix(results),
        suggested_actions(results),
        "",
        "## Scope notes",
        "",
        "- This report is deterministic QC only. It does not modify/clean data, judge answer quality, detect prompt injection, validate factual correctness, or replace human sampling.",
        "- Prompt-completion semantic alignment and ML-based PII detection are intentionally out of scope.",
    ]
    report = "\n".join(lines).rstrip() + "\n"
    if output:
        Path(output).write_text(report, encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Aggregate JSON check outputs into final markdown report")
    parser.add_argument("results", nargs="+", help="Result JSON file(s) or directory containing result JSON files")
    parser.add_argument("--output", "-o", help="Markdown report output path")
    parser.add_argument("--config", help="Accepted for interface consistency; unused")
    parser.add_argument("--sample-size", type=int, default=None, help="Accepted for interface consistency; unused")
    args = parser.parse_args()
    results = load_results(args.results)
    report = write_report(results, args.output)
    eprint(f"[OK] generate_report: wrote {args.output or 'stdout'}")
    print(report)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
