---
name: shoko-md
description: Run comprehensive quality control for fine-tuning datasets. Use whenever the user asks to check, validate, audit, QC, review, vet, or sanity check fine-tuning data, training data, SFT data, instruction data, chat datasets, completion datasets, preference data, DPO data, RLHF data, or classification fine-tunes; uploads jsonl, json, csv, tsv, parquet, or arrow files in a training context; passes train, val, test, or dev splits; or asks to find duplicates, leakage, PII, or format problems in training data. Do not use for ordinary business datasets, logs, generic data analysis, pretraining-scale corpora, or inference-time eval sets unless framed as fine-tune eval QC.
compatibility: Requires Python 3.10+. Optional dependencies are listed in requirements.txt; scripts degrade gracefully for missing tiktoken, datasketch, or pyarrow where possible.
metadata:
  display_name: shoko.md
---

# shoko.md

Run deterministic quality control on fine-tuning datasets for SFT, instruction tuning, chat data, prompt-completion data, DPO/RLHF preference pairs, and classification fine-tunes. The skill is a checklist plus toolbox: scripts compute scale-dependent facts exactly where possible, and Claude interprets severity and remediation priorities.

Lean on the scripts rather than eyeballing the data. Counts, duplicate rates, and leakage are easy to misjudge by hand, and a wrong number in a QC report is worse than no number — so let the scripts compute the facts and spend your effort interpreting them.

## Scope

This skill handles fine-tuning quantities, roughly up to low millions of examples. For huge files above the configured safety limit, stream what can be streamed and refuse checks that would likely OOM instead of crashing.

This skill does not:

- Modify or clean the dataset. It only reports.
- Judge whether responses are good; no LLM-as-judge calls.
- Detect prompt injection or jailbreak attempts in training data.
- Validate factual correctness of completions.
- Handle pretraining-scale corpora.
- Replace human review. Always recommend manual inspection of 20-50 random records.

Prompt-completion semantic alignment and ML-based PII detection are explicitly out of scope.

## Supported inputs

Files: `.jsonl`, `.json`, `.csv`, `.tsv`, `.parquet`, `.arrow`, and line-delimited raw text.

Detected formats:

- OpenAI chat JSONL with `messages` arrays and `system`, `user`, `assistant`, or `tool` roles.
- Anthropic-style chat with alternate role names or `human` and `assistant` fields.
- Prompt-completion pairs such as `prompt` plus `completion`, `input` plus `output`, `instruction` plus `response`, or `question` plus `answer`.
- Preference pairs such as `prompt`, `chosen`, `rejected`.
- Classification rows such as `text`, `label`.
- Raw text, one document per line.

Read `references/formats.md` when input format is unclear.

## Workflow decision tree

1. Run `scripts/detect_format.py` on each file. If any file is mixed-format, treat it as CRITICAL and stop format-specific checks for that file.
2. If multiple files were passed, or a single file contains a `split` field, run `scripts/split_leakage.py` next. Leakage between train and test is usually the highest-impact bug.
3. Run universal checks: schema, encoding, exact duplicates, near duplicates, length stats, empty/trivial content, and PII scan.
4. Run only the relevant format-specific checks:
   - Chat: `scripts/chat_format_check.py`
   - Preference pairs: `scripts/preference_pair_check.py`
   - Classification: `scripts/classification_check.py`
   - Prompt-completion: `scripts/prompt_completion_check.py`
5. Generate the consolidated markdown report with `scripts/generate_report.py`, or run everything through `scripts/run_all.py`.
6. In Suggested next actions, prioritize CRITICAL findings first, then WARNINGs by likely fine-tune harm and ease of repair.

## Fast path

Use the one-command runner unless the user asks for a custom sequence:

```bash
python scripts/run_all.py /path/to/dataset-or-directory --output-dir qc-results --sample-size 5
```

The runner writes per-check JSON, stderr logs, `manual_review_samples.json`, `effective_config.json`, `run_all_summary.json`, and `report.md`. Pass `--skip-near` to skip the near-duplicate pass on large datasets.

For declared classification labels or custom thresholds:

```bash
python scripts/run_all.py data/ --config .shoko.config.json --output-dir qc-results
```

Config files use `.shoko.config.json` — `~/.shoko.config.json` and the current directory's `.shoko.config.json` are auto-discovered and merged over the defaults (local overrides global), or pass a JSON/YAML file explicitly via `--config`.

Example:

```json
{
  "near_duplicate_threshold": 0.85,
  "min_trivial_chars": 3,
  "declared_labels": ["negative", "neutral", "positive"],
  "max_file_size_gb": 1.0
}
```

## Script contract

Every script in `scripts/` is standalone:

```bash
python scripts/<name>.py <input> --config .shoko.config.json --sample-size 5
```

Each script emits machine-readable JSON to stdout and a human-readable summary to stderr. Scripts exit nonzero on CRITICAL issues so they can be chained, but `run_all.py` continues after nonzero exits to produce a complete report.

## Universal checks

Run these on every dataset:

- `validate_schema.py`: required fields, types, nulls, valid JSONL lines, empty/trivial fields, accidental special tokens.
- `encoding_check.py`: UTF-8, mojibake, BOMs, NULL bytes.
- `dedup_exact.py`: full-record hash duplicates.
- `dedup_near.py`: MinHash LSH using `datasketch` when installed; fallback Jaccard for small files.
- `length_stats.py`: character and token stats, using `tiktoken` with `cl100k_base` when available and a clearly labeled chars/4 heuristic otherwise.
- `pii_scan.py`: regex scan for emails, phone numbers, US SSNs, credit cards with Luhn, IPs, common API keys, and loose street-address heuristics. Samples are redacted.
- `split_leakage.py`: exact and near-duplicate leakage across train, val, dev, and test files or logical split fields.

## Severity rubric

Use this rubric consistently. Read `references/severity_rubric.md` for more examples.

- CRITICAL: breaks the fine-tune or produces wrong training signal. Examples: schema invalid, mixed format, chosen equals rejected, exact leakage between train and test, empty file.
- WARNING: likely degrades quality but training may still run. Examples: high near-dup rate, class imbalance, length outliers, PII/secrets, special token contamination, chat role mistakes that may be filtered by the training API.
- INFO: worth knowing but not necessarily actionable. Examples: system prompt count, tokenizer fallback note, manual preference-pair review samples.
- OK: check completed without findings.

## Report requirements

The final markdown report should contain:

1. Header: file names, record counts, detected formats, timestamp.
2. Summary table: one row per check with severity and one-line finding.
3. Critical issues: details and up to 5 concrete examples per issue, with PII redacted.
4. Warnings: details and examples.
5. Stats appendix: length distributions, token counts, class balance, split leakage tables, and compact histograms where useful.
6. Suggested next actions: prioritized fixes, not a generic checklist.
7. Manual review reminder: tell the user to inspect 20-50 random records. `run_all.py` writes `manual_review_samples.json`.

## Interpretation guidance

Use references on demand:

- `references/formats.md` for supported row shapes and examples.
- `references/severity_rubric.md` for consistent CRITICAL/WARNING/INFO decisions.
- `references/common_pitfalls.md` for common dataset bugs and what they imply.

When presenting results to the user, be direct about limitations. For example, regex PII scans have false positives and miss non-US or non-English identifiers; prompt-completion semantic alignment is not checked; and DPO chosen/rejected quality still needs human sampling.

## Example and smoke test

This skill includes a planted-issue example under `examples/`:

```bash
python scripts/run_all.py examples --output-dir /tmp/shoko.md-smoke --sample-size 5
```

Expected catches include cross-split leakage, exact duplicates, near duplicates, PII/API keys, special tokens, role alternation failures, empty assistant turns, completion copies prompt, and chosen/rejected equality in the preference example.
