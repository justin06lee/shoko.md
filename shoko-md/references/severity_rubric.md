# Severity rubric

Use these definitions consistently in reports and user-facing summaries.

## CRITICAL

A CRITICAL issue either breaks the fine-tune, prevents reliable ingestion, or teaches the wrong training signal.

Examples:

- Invalid JSONL lines or records not matching the detected schema.
- Mixed formats inside a single file.
- Empty file or zero usable records.
- `chosen` equals `rejected` in preference data.
- Exact leakage between train and test or validation/test splits.
- Required fields are null or have unsupported types.
- NULL bytes in text fields.
- Empty assistant messages in chat data when no tool/function call is present.

Recommended response: stop and fix before training.

## WARNING

A WARNING is likely to degrade quality, bias training, or create privacy/security risk, but a training job may still run.

Examples:

- Near duplicates inside a split or across splits.
- Class imbalance or label normalization drift.
- PII, secrets, IP addresses, or loose address matches.
- Long-tail length outliers exceeding common context windows.
- Completion copies prompt.
- Special token contamination such as `<|endoftext|>`.
- System prompt drift or many unique system prompts.
- Chosen answers systematically much longer than rejected answers.

Recommended response: fix when cheap; otherwise quantify and decide whether the risk is acceptable for the user’s fine-tune goal.

## INFO

INFO findings help interpretation but do not imply a problem by themselves.

Examples:

- Token counts used a chars/4 heuristic because `tiktoken` was unavailable.
- System prompt count and top system prompt excerpts.
- Manual review samples for chosen/rejected swap checks.
- PII scanner limitation notes.

Recommended response: mention briefly and connect to next actions only if relevant.

## OK

The check completed and did not find actionable issues.
