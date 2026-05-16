#!/usr/bin/env python3
"""Shared utilities for shoko.md fine-tuning dataset QC scripts."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import re
import statistics
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

SUPPORTED_EXTENSIONS = {".jsonl", ".json", ".csv", ".tsv", ".txt", ".parquet", ".arrow"}
TEXTISH_EXTENSIONS = {".jsonl", ".json", ".csv", ".tsv", ".txt"}

DEFAULT_CONFIG: Dict[str, Any] = {
    "near_duplicate_threshold": 0.85,
    "near_duplicate_num_perm": 128,
    "near_duplicate_max_records": 250000,
    "near_duplicate_fallback_max_records": 5000,
    "sample_size": 5,
    "min_trivial_chars": 3,
    "max_file_size_gb": 1.0,
    "length_windows": [4000, 8000, 32000, 128000, 200000],
    "token_encoding": "cl100k_base",
    "pii_sample_size": 5,
    "declared_labels": None,
    "classification_majority_minority_warning_ratio": 10.0,
    "preference_length_bias_warning_ratio": 0.35,
    "split_near_leakage_max_records_per_split": 50000,
    "random_review_sample": 25,
}

SPECIAL_TOKEN_PATTERNS = [
    "<|endoftext|>", "<|im_start|>", "<|im_end|>", "<s>", "</s>", "[INST]", "[/INST]"
]

MOJIBAKE_PATTERNS = ["Â", "â€™", "â€œ", "â€\u009d", "â€“", "â€”", "Ã©", "Ã¨", "Ã±", "ï»¿"]


@dataclass
class Record:
    record: Any
    source: str
    index: int
    line: Optional[int]
    raw: Optional[str] = None

    @property
    def loc(self) -> Dict[str, Any]:
        out = {"file": self.source, "index": self.index}
        if self.line is not None:
            out["line"] = self.line
        return out


def eprint(*args: Any, **kwargs: Any) -> None:
    print(*args, file=sys.stderr, **kwargs)


def emit_json(obj: Dict[str, Any]) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True))


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_config(path: Optional[str]) -> Dict[str, Any]:
    cfg = dict(DEFAULT_CONFIG)
    if path:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Config file not found: {path}")
        text = p.read_text(encoding="utf-8")
    else:
        # Auto-discover: global then local .shoko.config.json
        global_cfg = Path.home() / ".shoko.config.json"
        local_cfg = Path.cwd() / ".shoko.config.json"
        loaded = {}
        if global_cfg.exists():
            loaded.update(json.loads(global_cfg.read_text(encoding="utf-8") or "{}"))
        if local_cfg.exists():
            loaded.update(json.loads(local_cfg.read_text(encoding="utf-8") or "{}"))
        if not loaded:
            return cfg
        cfg.update(loaded)
        return cfg
    if p.suffix.lower() in {".yaml", ".yml"}:
        try:
            import yaml  # type: ignore
        except Exception as exc:
            raise RuntimeError("YAML config requires PyYAML. Use JSON config or install PyYAML.") from exc
        loaded = yaml.safe_load(text) or {}
    else:
        loaded = json.loads(text or "{}")
    if not isinstance(loaded, dict):
        raise ValueError("Config must be a JSON/YAML object")
    cfg.update(loaded)
    return cfg


def common_parser(description: str, multiple_inputs: bool = False) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    nargs = "+" if multiple_inputs else None
    parser.add_argument("input", nargs=nargs, help="Input dataset file or directory")
    parser.add_argument("--config", help="JSON or YAML config path")
    parser.add_argument("--sample-size", type=int, default=None, help="Maximum example count to return")
    return parser


def check_file_size(path: Path, cfg: Dict[str, Any]) -> Optional[str]:
    max_gb = float(cfg.get("max_file_size_gb", 1.0))
    try:
        size_gb = path.stat().st_size / (1024 ** 3)
    except FileNotFoundError:
        return f"File not found: {path}"
    if size_gb > max_gb:
        return f"{path} is {size_gb:.2f}GB, above configured max_file_size_gb={max_gb}; refusing checks that may OOM."
    return None


def list_input_files(path: str) -> List[str]:
    p = Path(path)
    if p.is_dir():
        files: List[Path] = []
        for ext in sorted(SUPPORTED_EXTENSIONS):
            files.extend(p.rglob(f"*{ext}"))
        # Keep stable order with common split names first.
        def sort_key(x: Path) -> Tuple[int, str]:
            name = x.name.lower()
            split_rank = 1
            for i, prefix in enumerate(["train", "val", "valid", "validation", "dev", "test"]):
                if name.startswith(prefix + ".") or name.startswith(prefix + "_") or name == prefix + x.suffix:
                    split_rank = i
                    break
            return (split_rank, str(x))
        return [str(f) for f in sorted(files, key=sort_key)]
    return [str(p)]


def iter_records(path: str, *, allow_json_errors: bool = False) -> Iterator[Record]:
    """Yield records from supported formats. JSONL errors are emitted as synthetic records only when allowed."""
    p = Path(path)
    suffix = p.suffix.lower()
    source = str(p)
    if suffix == ".jsonl":
        with p.open("r", encoding="utf-8", errors="replace", newline="") as fh:
            for i, line in enumerate(fh):
                raw = line.rstrip("\n")
                if not raw.strip():
                    yield Record({"__empty_line__": True}, source, i, i + 1, raw)
                    continue
                try:
                    rec = json.loads(raw)
                except json.JSONDecodeError as exc:
                    if allow_json_errors:
                        yield Record({"__json_error__": str(exc), "__raw__": raw}, source, i, i + 1, raw)
                        continue
                    raise
                yield Record(rec, source, i, i + 1, raw)
    elif suffix == ".json":
        # JSON is not stream-friendly by design. Fine for low-millions only if users keep files modest.
        with p.open("r", encoding="utf-8", errors="replace") as fh:
            data = json.load(fh)
        if isinstance(data, list):
            for i, rec in enumerate(data):
                yield Record(rec, source, i, None, None)
        elif isinstance(data, dict):
            if isinstance(data.get("data"), list):
                for i, rec in enumerate(data["data"]):
                    yield Record(rec, source, i, None, None)
            else:
                yield Record(data, source, 0, None, None)
        else:
            yield Record({"__raw_json__": data}, source, 0, None, None)
    elif suffix in {".csv", ".tsv"}:
        dialect = "excel-tab" if suffix == ".tsv" else "excel"
        with p.open("r", encoding="utf-8", errors="replace", newline="") as fh:
            reader = csv.DictReader(fh, dialect=dialect)
            for i, row in enumerate(reader):
                yield Record(dict(row), source, i, i + 2, None)
    elif suffix == ".txt":
        with p.open("r", encoding="utf-8", errors="replace") as fh:
            for i, line in enumerate(fh):
                yield Record({"text": line.rstrip("\n"), "__raw_text__": True}, source, i, i + 1, line.rstrip("\n"))
    elif suffix in {".parquet", ".arrow"}:
        try:
            import pyarrow.parquet as pq  # type: ignore
            import pyarrow.ipc as ipc  # type: ignore
        except Exception as exc:
            raise RuntimeError("pyarrow is required for .parquet/.arrow files") from exc
        if suffix == ".parquet":
            pf = pq.ParquetFile(p)
            idx = 0
            for batch in pf.iter_batches():
                rows = batch.to_pylist()
                for row in rows:
                    yield Record(row, source, idx, None, None)
                    idx += 1
        else:
            with p.open("rb") as fh:
                reader = ipc.open_file(fh)
                idx = 0
                for batch_i in range(reader.num_record_batches):
                    rows = reader.get_batch(batch_i).to_pylist()
                    for row in rows:
                        yield Record(row, source, idx, None, None)
                        idx += 1
    else:
        raise ValueError(f"Unsupported extension {suffix}: {path}")


def is_synthetic_record(record: Any) -> bool:
    """True for placeholder records iter_records yields for blank lines or JSON
    parse failures. These are surfaced by schema validation; hashing or
    comparing them elsewhere would invent false duplicates and false leakage."""
    return isinstance(record, dict) and ("__empty_line__" in record or "__json_error__" in record)


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def record_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8", errors="replace")).hexdigest()


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def get_path_value(record: Any, path: str) -> Any:
    cur = record
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    return canonical_json(value)


def extract_messages(record: Any) -> List[Dict[str, Any]]:
    if isinstance(record, dict) and isinstance(record.get("messages"), list):
        return [m for m in record["messages"] if isinstance(m, dict)]
    if isinstance(record, dict) and isinstance(record.get("conversation"), list):
        return [m for m in record["conversation"] if isinstance(m, dict)]
    return []


def message_role(msg: Dict[str, Any]) -> str:
    role = msg.get("role") or msg.get("speaker") or msg.get("from") or msg.get("type")
    role = stringify(role).lower().strip()
    mapping = {"human": "user", "user": "user", "assistant": "assistant", "bot": "assistant", "ai": "assistant", "system": "system", "tool": "tool", "function": "tool"}
    return mapping.get(role, role)


def message_content(msg: Dict[str, Any]) -> str:
    if "content" in msg:
        return stringify(msg.get("content"))
    if "text" in msg:
        return stringify(msg.get("text"))
    if "value" in msg:
        return stringify(msg.get("value"))
    return ""


def text_fields(record: Any) -> Dict[str, str]:
    """Return known textual fields for a fine-tuning record."""
    out: Dict[str, str] = {}
    if isinstance(record, str):
        out["text"] = record
        return out
    if not isinstance(record, dict):
        return out
    msgs = extract_messages(record)
    if msgs:
        parts = []
        for i, msg in enumerate(msgs):
            role = message_role(msg)
            content = message_content(msg)
            out[f"messages[{i}].content"] = content
            parts.append(f"{role}: {content}")
        out["messages_joined"] = "\n".join(parts)
    for key in ["prompt", "completion", "input", "output", "chosen", "rejected", "text", "label", "instruction", "response", "question", "answer"]:
        if key in record:
            out[key] = stringify(record.get(key))
    if not out:
        for key, value in record.items():
            if isinstance(value, str):
                out[key] = value
    return out


def primary_input_text(record: Any) -> str:
    fields = text_fields(record)
    for key in ["prompt", "input", "instruction", "question", "text", "messages_joined"]:
        if key in fields and fields[key].strip():
            return fields[key]
    return "\n".join(v for v in fields.values() if isinstance(v, str))


def record_text_bundle(record: Any) -> str:
    fields = text_fields(record)
    if not fields:
        return canonical_json(record)
    return "\n".join(f"{k}: {v}" for k, v in fields.items())


def detect_record_format(record: Any) -> str:
    if isinstance(record, dict) and (record.get("__json_error__") or record.get("__empty_line__")):
        return "invalid"
    if isinstance(record, dict):
        keys = set(record.keys())
        msgs = extract_messages(record)
        if msgs:
            roles = {message_role(m) for m in msgs}
            if roles and roles <= {"system", "user", "assistant", "tool"}:
                return "openai_chat"
            return "anthropic_chat"
        if {"human", "assistant"} <= keys:
            return "anthropic_chat"
        if "chosen" in keys and "rejected" in keys and ("prompt" in keys or "input" in keys or "question" in keys):
            return "preference_pair"
        if {"prompt", "completion"} <= keys or {"input", "output"} <= keys or {"instruction", "response"} <= keys:
            return "prompt_completion"
        if "text" in keys and "label" in keys:
            return "classification"
        if record.get("__raw_text__"):
            return "raw_text"
        if len(keys) == 1 and next(iter(keys), "") in {"text", "document", "content"}:
            return "raw_text"
    if isinstance(record, str):
        return "raw_text"
    return "unknown"


def detect_file_format(path: str, sample_size: int = 2000) -> Dict[str, Any]:
    counts: Counter[str] = Counter()
    examples: Dict[str, Any] = {}
    total = 0
    json_errors: List[Dict[str, Any]] = []
    try:
        for wrapped in iter_records(path, allow_json_errors=True):
            total += 1
            tag = detect_record_format(wrapped.record)
            counts[tag] += 1
            examples.setdefault(tag, wrapped.loc)
            if tag == "invalid":
                json_errors.append({**wrapped.loc, "error": wrapped.record.get("__json_error__")})
            if total >= sample_size:
                break
    except Exception as exc:
        return {"file": path, "format": "unreadable", "format_counts": {}, "record_count_sampled": total, "critical": True, "issues": [{"severity": "CRITICAL", "message": str(exc)}]}
    meaningful = {k: v for k, v in counts.items() if k not in {"unknown"}}
    issues = []
    critical = False
    if total == 0:
        critical = True
        fmt = "empty"
        issues.append({"severity": "CRITICAL", "message": "File has 0 records"})
    elif counts.get("invalid", 0):
        critical = True
        fmt = "invalid"
        issues.append({"severity": "CRITICAL", "message": f"Invalid JSON/empty-line records in sample: {counts['invalid']}", "examples": json_errors[:5]})
    elif len(meaningful) > 1:
        critical = True
        fmt = "mixed"
        issues.append({"severity": "CRITICAL", "message": "Mixed dataset formats within one file", "format_counts": dict(counts), "examples": examples})
    elif meaningful:
        fmt = max(meaningful.items(), key=lambda kv: kv[1])[0]
    else:
        fmt = "unknown"
        issues.append({"severity": "WARNING", "message": "Could not confidently detect a supported fine-tuning format"})
    return {"file": path, "format": fmt, "format_counts": dict(counts), "record_count_sampled": total, "critical": critical, "issues": issues}


def tokenize_words(text: str) -> List[str]:
    return re.findall(r"[\w']+", (text or "").lower(), flags=re.UNICODE)


def token_shingles(text: str, n: int = 5) -> set[str]:
    toks = tokenize_words(text)
    if len(toks) < n:
        return set(toks)
    return {" ".join(toks[i:i+n]) for i in range(len(toks) - n + 1)}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def bounded_repr(value: Any, max_chars: int = 500) -> str:
    s = canonical_json(value) if not isinstance(value, str) else value
    if len(s) > max_chars:
        return s[:max_chars] + "..."
    return s


def sanitize_sample(record: Any, max_chars: int = 800) -> Any:
    return redact_text(bounded_repr(record, max_chars=max_chars))


def reservoir_sample(items: Iterable[Record], k: int) -> List[Dict[str, Any]]:
    sample: List[Dict[str, Any]] = []
    for n, item in enumerate(items, start=1):
        entry = {"loc": item.loc, "record": sanitize_sample(item.record)}
        if len(sample) < k:
            sample.append(entry)
        else:
            j = random.randint(1, n)
            if j <= k:
                sample[j - 1] = entry
    return sample


def percentile(values: Sequence[float], p: float) -> Optional[float]:
    if not values:
        return None
    vals = sorted(values)
    if len(vals) == 1:
        return vals[0]
    rank = (len(vals) - 1) * p / 100.0
    lo = math.floor(rank)
    hi = math.ceil(rank)
    if lo == hi:
        return vals[int(rank)]
    return vals[lo] + (vals[hi] - vals[lo]) * (rank - lo)


def basic_stats(values: Sequence[float]) -> Dict[str, Optional[float]]:
    return {
        "count": len(values),
        "p50": percentile(values, 50),
        "p90": percentile(values, 90),
        "p99": percentile(values, 99),
        "max": max(values) if values else None,
        "mean": statistics.mean(values) if values else None,
    }


def luhn_ok(number: str) -> bool:
    digits = [int(c) for c in re.sub(r"\D", "", number)]
    if len(digits) < 13 or len(digits) > 19:
        return False
    checksum = 0
    parity = len(digits) % 2
    for i, d in enumerate(digits):
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    return checksum % 10 == 0


EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{2,4}\)?[\s.-]?){2,4}\d{2,4}(?!\w)")
SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
CC_RE = re.compile(r"\b(?:\d[ -]*?){13,19}\b")
IPV4_RE = re.compile(r"\b(?:25[0-5]|2[0-4]\d|[01]?\d?\d)(?:\.(?:25[0-5]|2[0-4]\d|[01]?\d?\d)){3}\b")
IPV6_RE = re.compile(r"\b(?:[0-9a-f]{1,4}:){2,7}[0-9a-f]{1,4}\b", re.I)
API_KEY_RE = re.compile(r"\b(?:sk-[A-Za-z0-9_-]{16,}|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,}|xoxb-[A-Za-z0-9-]{20,}|AIza[0-9A-Za-z_-]{20,})\b")
STREET_RE = re.compile(r"\b\d{1,6}\s+[A-Za-z0-9.'-]+(?:\s+[A-Za-z0-9.'-]+){0,4}\s+(?:Street|St\.?|Avenue|Ave\.?|Road|Rd\.?|Boulevard|Blvd\.?|Drive|Dr\.?|Lane|Ln\.?|Court|Ct\.?|Way|Place|Pl\.?|Circle|Cir\.?)\b", re.I)


def redact_text(text: str) -> str:
    def cc_sub(m: re.Match[str]) -> str:
        s = m.group(0)
        return "[REDACTED_CREDIT_CARD]" if luhn_ok(s) else s
    text = EMAIL_RE.sub("[REDACTED_EMAIL]", text)
    text = SSN_RE.sub("[REDACTED_SSN]", text)
    text = API_KEY_RE.sub("[REDACTED_API_KEY]", text)
    text = IPV4_RE.sub("[REDACTED_IPV4]", text)
    text = IPV6_RE.sub("[REDACTED_IPV6]", text)
    text = CC_RE.sub(cc_sub, text)
    text = PHONE_RE.sub("[REDACTED_PHONE]", text)
    text = STREET_RE.sub("[REDACTED_STREET_ADDRESS]", text)
    return text


def severity_rank(sev: str) -> int:
    return {"OK": 0, "INFO": 1, "WARNING": 2, "CRITICAL": 3}.get(sev.upper(), 1)


def check_result(check: str, severity: str, finding: str, **kwargs: Any) -> Dict[str, Any]:
    out = {"check": check, "severity": severity, "finding": finding}
    out.update(kwargs)
    return out


def exit_for_severity(results: Dict[str, Any]) -> int:
    def walk(obj: Any) -> bool:
        if isinstance(obj, dict):
            if obj.get("severity") == "CRITICAL" or obj.get("critical") is True:
                return True
            return any(walk(v) for v in obj.values())
        if isinstance(obj, list):
            return any(walk(x) for x in obj)
        return False
    return 2 if walk(results) else 0


def split_name_from_path(path: str) -> str:
    name = Path(path).name.lower()
    for split in ["train", "validation", "valid", "val", "dev", "test"]:
        if name == split or name.startswith(split + ".") or name.startswith(split + "_") or name.startswith(split + "-"):
            return "val" if split in {"validation", "valid"} else split
    return Path(path).stem
