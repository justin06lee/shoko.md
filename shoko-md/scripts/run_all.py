#!/usr/bin/env python3
from qc_utils import *
import subprocess

SCRIPT_DIR = Path(__file__).resolve().parent
UNIVERSAL = [
    "detect_format.py",
    "encoding_check.py",
    "validate_schema.py",
    "dedup_exact.py",
    "dedup_near.py",
    "length_stats.py",
    "pii_scan.py",
]
FORMAT_SCRIPTS = {
    "openai_chat": ["chat_format_check.py"],
    "anthropic_chat": ["chat_format_check.py"],
    "preference_pair": ["preference_pair_check.py"],
    "classification": ["classification_check.py"],
    "prompt_completion": ["prompt_completion_check.py"],
    "raw_text": [],
}


SPLIT_NAMES = {"train", "val", "dev", "test"}


def run_script(script: str, inputs: List[str], out_dir: Path, cfg_path: Optional[str], sample_size: Optional[int], output_stem: Optional[str] = None) -> Tuple[Optional[Dict[str, Any]], int]:
    cmd = [sys.executable, str(SCRIPT_DIR / script)] + inputs
    if cfg_path:
        cmd.extend(["--config", cfg_path])
    if sample_size is not None:
        cmd.extend(["--sample-size", str(sample_size)])
    eprint(f"Running {script} ...")
    proc = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stem = output_stem or Path(script).stem
    (out_dir / f"{stem}.stderr.txt").write_text(proc.stderr, encoding="utf-8")
    try:
        data = json.loads(proc.stdout)
    except Exception as exc:
        data = {"script": script, "summary": check_result(stem, "CRITICAL", f"Script did not emit valid JSON: {exc}"), "stdout": proc.stdout[:5000], "stderr": proc.stderr[:5000], "returncode": proc.returncode}
    data["returncode"] = proc.returncode
    (out_dir / f"{stem}.json").write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    if proc.stderr:
        eprint(proc.stderr.rstrip())
    if proc.returncode not in (0, 2):
        eprint(f"{script} exited {proc.returncode}; continuing so the report can show partial results.")
    return data, proc.returncode


def is_split_named(path: str) -> bool:
    return split_name_from_path(path) in SPLIT_NAMES


def file_has_split_field(path: str, sample_limit: int = 2000) -> bool:
    try:
        for i, wrapped in enumerate(iter_records(path, allow_json_errors=True)):
            if i >= sample_limit:
                break
            if isinstance(wrapped.record, dict) and wrapped.record.get("split") is not None:
                return True
    except Exception:
        return False
    return False


def split_leakage_jobs(inputs: List[str], detect: Dict[str, Any]) -> List[Tuple[str, List[str]]]:
    formats_by_file = {
        f.get("file"): f.get("format")
        for f in detect.get("files", [])
        if f.get("format") not in {"mixed", "invalid", "empty", "unknown", "unreadable", "too_large"}
    }
    groups: Dict[str, List[str]] = defaultdict(list)
    for path in inputs:
        fmt = formats_by_file.get(path)
        if fmt:
            groups[fmt].append(path)

    jobs: List[Tuple[str, List[str]]] = []
    for fmt, files in sorted(groups.items()):
        split_field_files = [f for f in files if file_has_split_field(f)]
        if split_field_files:
            jobs.append((f"split_leakage_{fmt}", split_field_files))
            continue
        named = [f for f in files if is_split_named(f)]
        if len({split_name_from_path(f) for f in named}) >= 2:
            jobs.append((f"split_leakage_{fmt}", named))
    return jobs


def write_random_review_samples(inputs: List[str], out_dir: Path, cfg: Dict[str, Any]) -> None:
    k = int(cfg.get("random_review_sample", 25))
    samples = []
    for f in inputs:
        try:
            sample = reservoir_sample(iter_records(f, allow_json_errors=True), max(1, k // max(1, len(inputs))))
            samples.extend(sample)
        except Exception as exc:
            samples.append({"loc": {"file": f}, "error": str(exc)})
    (out_dir / "manual_review_samples.json").write_text(json.dumps(samples[:k], ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run all fine-tuning dataset QC checks and generate a markdown report")
    parser.add_argument("input", help="Input dataset file or directory")
    parser.add_argument("--output-dir", "-o", default="qc-results", help="Directory for JSON outputs and report")
    parser.add_argument("--config", help="JSON/YAML config path")
    parser.add_argument("--sample-size", type=int, default=None, help="Examples per issue")
    parser.add_argument("--skip-near", action="store_true", help="Skip near duplicate and near leakage checks for very large files")
    args = parser.parse_args()
    cfg = load_config(args.config)
    if args.sample_size is not None:
        cfg["sample_size"] = args.sample_size
    out_dir = Path(args.output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    inputs = list_input_files(args.input)
    if not inputs:
        eprint("No supported dataset files found.")
        emit_json({"script": "run_all.py", "summary": check_result("run_all", "CRITICAL", "No supported dataset files found")})
        return 2
    cfg_run_path = out_dir / "effective_config.json"
    cfg_run_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    cfg_path = str(cfg_run_path)
    scripts = list(UNIVERSAL)
    if args.skip_near:
        scripts = [s for s in scripts if s != "dedup_near.py"]
    results = []
    max_rc = 0
    for script in scripts:
        data, rc = run_script(script, inputs, out_dir, cfg_path, args.sample_size)
        results.append(data)
        max_rc = max(max_rc, rc)
    # Decide relevant format-specific checks from detect_format output.
    detected = set()
    detect = next((r for r in results if r.get("script") == "detect_format.py"), {})
    if args.skip_near:
        eprint("Skipping split leakage because --skip-near was set.")
    else:
        jobs = split_leakage_jobs(inputs, detect)
        if jobs:
            for stem, files in jobs:
                data, rc = run_script("split_leakage.py", files, out_dir, cfg_path, args.sample_size, output_stem=stem)
                results.append(data)
                max_rc = max(max_rc, rc)
        else:
            eprint("Skipping split_leakage.py because no train/val/test/dev split grouping was detected.")
    for f in detect.get("files", []):
        fmt = f.get("format")
        if fmt in FORMAT_SCRIPTS:
            detected.add(fmt)
        elif fmt in {"mixed", "invalid", "empty"}:
            eprint(f"Skipping format-specific checks for {f.get('file')} because detected format is {fmt}.")
    format_scripts = []
    for fmt in sorted(detected):
        format_scripts.extend(FORMAT_SCRIPTS.get(fmt, []))
    for script in sorted(set(format_scripts)):
        data, rc = run_script(script, inputs, out_dir, cfg_path, args.sample_size)
        results.append(data)
        max_rc = max(max_rc, rc)
    write_random_review_samples(inputs, out_dir, cfg)
    # Generate report from JSONs.
    report_path = out_dir / "report.md"
    cmd = [sys.executable, str(SCRIPT_DIR / "generate_report.py"), str(out_dir), "--output", str(report_path)]
    proc = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (out_dir / "generate_report.stdout.md").write_text(proc.stdout, encoding="utf-8")
    (out_dir / "generate_report.stderr.txt").write_text(proc.stderr, encoding="utf-8")
    eprint(proc.stderr.rstrip())
    eprint(f"Report: {report_path}")
    summary = {"script": "run_all.py", "timestamp": now_iso(), "inputs": inputs, "output_dir": str(out_dir), "report": str(report_path), "returncode_max": max_rc}
    (out_dir / "run_all_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 2 if any(summary_from_result(r).get("severity") == "CRITICAL" for r in results if isinstance(r, dict)) else 0

# Local copy to avoid import cycle with generate_report.
def summary_from_result(res: Dict[str, Any]) -> Dict[str, str]:
    summary = res.get("summary") or {}
    return {"check": str(summary.get("check") or Path(str(res.get("script", "unknown"))).stem), "severity": str(summary.get("severity", "INFO")), "finding": str(summary.get("finding", ""))}

if __name__ == "__main__":
    raise SystemExit(main())
