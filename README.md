<div align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="shoko.png">
    <img alt="shoko.md" src="shoko.png" width="360">
  </picture>

  # shoko.md

  Deterministic quality control for fine-tuning datasets.

  A [Claude Code](https://docs.claude.com/en/docs/claude-code/skills) skill that audits training data for SFT, instruction tuning, chat, DPO/RLHF preference pairs, classification, and prompt-completion formats — no LLM-as-judge, just exact checks and a severity rubric.
</div>

---

## What it does

Point shoko.md at a dataset and it detects the format, runs the relevant checks, and produces a single markdown report. It catches the structural bugs that quietly ruin a fine-tune: train/test leakage, duplicates, broken chat roles, empty completions, `chosen == rejected`, PII, special-token contamination, and more.

The scripts compute exact facts (counts, duplicate rates, leakage). Claude interprets severity and prioritizes fixes. It **reports only** — it never modifies your data.

---

## Install

### With [bmo](https://github.com/justin06lee/bmo) (recommended)

`bmo` is a tiny installer for Claude Code skills.

```bash
# Preview the skill before installing
bmo inspect justin06lee/shoko.md

# Install globally (into ~/.claude/skills/)
bmo add justin06lee/shoko.md

# Or install into the current project (./.claude/skills/)
bmo add --project justin06lee/shoko.md
```

Installing from a local clone works too — point bmo at the skill **directory**:

```bash
bmo add ./shoko.md/shoko-md
```

### Without bmo

A Claude Code skill is just a folder containing a `SKILL.md`. Copy the `shoko-md/` directory into your skills directory:

```bash
git clone https://github.com/justin06lee/shoko.md
cp -r shoko.md/shoko-md ~/.claude/skills/shoko-md
```

---

## Usage

Once installed, ask Claude Code to QC a dataset:

> "QC this chat dataset before I train on it"
>
> "Audit this DPO preference file for bugs"
>
> "Validate this classification CSV"

The skill handles dataset loading, format detection, and running the right checks automatically, then hands you a prioritized report.

---

## Checks

| Check | What it finds | Severity range |
|---|---|---|
| `validate_schema.py` | Required fields, types, nulls, valid JSONL, empty/trivial fields | CRITICAL–OK |
| `encoding_check.py` | Mojibake, BOMs, NULL bytes | CRITICAL–OK |
| `dedup_exact.py` | Full-record hash duplicates | WARNING–OK |
| `dedup_near.py` | MinHash LSH near-duplicates | WARNING–OK |
| `length_stats.py` | Character/token length outliers | WARNING–OK |
| `pii_scan.py` | Emails, phone numbers, SSNs, credit cards, API keys, addresses | WARNING–OK |
| `split_leakage.py` | Cross-split exact and near-duplicate leakage | CRITICAL–OK |
| `chat_format_check.py` | Role alternation, empty assistant turns, tool call types | CRITICAL–OK |
| `preference_pair_check.py` | Chosen=rejected, conflicting prompt pairs | CRITICAL–OK |
| `classification_check.py` | Label normalization drift, class balance | WARNING–OK |
| `prompt_completion_check.py` | Empty completions, prompt copying | CRITICAL–OK |

---

## Supported input formats

`.jsonl`, `.json`, `.csv`, `.tsv`, `.parquet`, `.arrow`, and line-delimited raw text.

Auto-detected shapes: OpenAI chat, Anthropic-style chat, prompt-completion pairs, preference pairs, classification rows, and raw text.

---

## Severity rubric

- **CRITICAL** — breaks the fine-tune or produces wrong training signal
- **WARNING** — likely degrades quality; training may still run
- **INFO** — worth knowing but not necessarily actionable
- **OK** — check completed without findings

---

## Configuration

Configuration is optional. shoko.md auto-discovers `.shoko.config.json` in the current directory, falling back to `~/.shoko.config.json` (local overrides global). You can also pass one explicitly with `--config`.

```json
{
  "near_duplicate_threshold": 0.85,
  "min_trivial_chars": 3,
  "declared_labels": ["negative", "neutral", "positive"],
  "max_file_size_gb": 1.0
}
```

---

## Running the scripts directly

The QC scripts are standalone Python — no Claude Code required.

```bash
# Run every check on a dataset directory
python shoko-md/scripts/run_all.py /path/to/dataset --output-dir qc-results

# Try it on the bundled example data (has planted issues)
python shoko-md/scripts/run_all.py shoko-md/examples --output-dir qc-results --sample-size 5
```

This writes per-check JSON, stderr logs, `manual_review_samples.json`, and a consolidated `report.md`.

You can also run individual checks:

```bash
python shoko-md/scripts/split_leakage.py /path/to/dataset
python shoko-md/scripts/pii_scan.py /path/to/dataset
python shoko-md/scripts/dedup_exact.py /path/to/dataset
```

All dependencies are optional — see `shoko-md/requirements.txt`. Scripts degrade gracefully when a package is missing (e.g. dedup falls back to pairwise Jaccard without `datasketch`).

---

## Eval results

Benchmarked across 3 eval cases (chat QC, DPO audit, classification validation):

| Metric | With skill | Without skill | Delta |
|---|---|---|---|
| Pass rate | 89% | 22% | **+67%** |
| Time | 8.5s | 33.3s | **−24.8s** |
| Tokens | 12.5K | 20.7K | **−8.2K** |

---

## Out of scope

- Modifying or cleaning the dataset (report-only)
- LLM-as-judge response quality evaluation
- Prompt injection or jailbreak detection
- Factual correctness of completions
- Semantic alignment for prompt-completion pairs
- ML-based PII detection (regex only)
- Pretraining-scale corpora
</content>
</invoke>
