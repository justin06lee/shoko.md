#!/usr/bin/env python3
from qc_utils import *


def get_token_counter(cfg: Dict[str, Any]):
    try:
        import tiktoken  # type: ignore
        enc = tiktoken.get_encoding(cfg.get("token_encoding", "cl100k_base"))
        return lambda s: len(enc.encode(s or "")), False, cfg.get("token_encoding", "cl100k_base")
    except Exception:
        return lambda s: math.ceil(len(s or "") / 4), True, "chars_div_4_heuristic"


def ascii_hist(values: List[int], bins: int = 10, width: int = 30) -> List[str]:
    if not values:
        return []
    lo, hi = min(values), max(values)
    if lo == hi:
        return [f"{lo:>7}-{hi:<7} | {'#' * min(width, len(values))} {len(values)}"]
    bins = min(bins, max(1, int(hi - lo)))
    step = (hi - lo) / bins
    counts = [0] * bins
    for v in values:
        idx = min(bins - 1, int((v - lo) / step))
        counts[idx] += 1
    m = max(counts) or 1
    lines = []
    for i, c in enumerate(counts):
        a = int(lo + i * step)
        b = int(lo + (i + 1) * step)
        bar = "#" * max(1, int(c / m * width)) if c else ""
        lines.append(f"{a:>7}-{b:<7} | {bar} {c}")
    return lines


def length_file(path: str, cfg: Dict[str, Any], sample_size: int) -> Dict[str, Any]:
    token_count, approximate, tokenizer = get_token_counter(cfg)
    chars: List[int] = []
    tokens: List[int] = []
    field_missing = 0
    longest: List[Tuple[int, Dict[str, Any], str]] = []
    windows = [int(x) for x in cfg.get("length_windows", [4000, 8000, 32000, 128000, 200000])]
    exceed = Counter()
    total = 0
    try:
        for wrapped in iter_records(path, allow_json_errors=True):
            total += 1
            text = record_text_bundle(wrapped.record)
            if not text:
                field_missing += 1
            c = len(text)
            t = token_count(text)
            chars.append(c)
            tokens.append(t)
            for w in windows:
                if t > w:
                    exceed[str(w)] += 1
            longest.append((t, wrapped.loc, redact_text(text[:500])))
            longest = sorted(longest, key=lambda x: x[0], reverse=True)[:sample_size]
    except Exception as exc:
        return {"file": path, "severity": "CRITICAL", "finding": str(exc), "error": str(exc)}
    severity = "WARNING" if any(exceed.values()) else "OK"
    finding = "Length outliers exceed common context windows" if severity == "WARNING" else "Length distribution computed"
    if approximate:
        finding += " using approximate token heuristic"
    return {
        "file": path,
        "record_count": total,
        "severity": severity,
        "finding": finding,
        "tokenizer": tokenizer,
        "token_counts_are_approximate": approximate,
        "char_stats": basic_stats(chars),
        "token_stats": basic_stats(tokens),
        "context_window_exceed_counts": dict(exceed),
        "empty_text_bundle_records": field_missing,
        "longest_examples": [{"token_count": t, "loc": loc, "text_excerpt": ex} for t, loc, ex in longest],
        "char_histogram": ascii_hist(chars),
        "token_histogram": ascii_hist(tokens),
    }


def main() -> int:
    parser = common_parser("Compute character and token length distributions", multiple_inputs=True)
    args = parser.parse_args()
    cfg = load_config(args.config)
    sample_size = args.sample_size or cfg.get("sample_size", 5)
    files = []
    for inp in (args.input if isinstance(args.input, list) else [args.input]):
        files.extend(list_input_files(inp))
    results = [length_file(f, cfg, sample_size) for f in files]
    severity = "CRITICAL" if any(r["severity"] == "CRITICAL" for r in results) else ("WARNING" if any(r["severity"] == "WARNING" for r in results) else "OK")
    eprint(f"[{severity}] length_stats: {sum(r.get('record_count', 0) for r in results)} record(s)")
    out = {"script": "length_stats.py", "timestamp": now_iso(), "files": results, "summary": check_result("length_distribution", severity, "Length stats computed")}
    emit_json(out)
    return exit_for_severity(out)

if __name__ == "__main__":
    raise SystemExit(main())
