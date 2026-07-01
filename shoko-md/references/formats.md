# Supported fine-tuning dataset formats

Use this reference to interpret `detect_format.py` output and decide which format-specific checks should run.

## OpenAI chat JSONL

One JSON object per line:

```json
{"messages":[{"role":"system","content":"You are concise."},{"role":"user","content":"Hi"},{"role":"assistant","content":"Hello!"}]}
```

Expected roles are `system`, `user`, `assistant`, and optionally `tool`. System messages should appear only at the start. The conversation should end on an assistant turn for supervised chat fine-tuning.

## Anthropic-style chat

Common shapes include `messages` or `conversation` arrays with role names like `human`, `assistant`, `user`, or `bot`, or simple rows containing `human` and `assistant` fields:

```json
{"human":"Summarize this note","assistant":"The note says..."}
```

The schema is less standardized, so detection is permissive. Role alternation and empty assistant checks still apply when messages can be extracted.

## Prompt-completion pairs

Supported key pairs:

```json
{"prompt":"Translate to French: cat","completion":"chat"}
{"input":"Translate to French: cat","output":"chat"}
{"instruction":"Translate to French","response":"chat"}
{"question":"Translate to French: cat","answer":"chat"}
```

The skill checks for empty completions and exact prompt copying. Semantic alignment is out of scope.

## Preference / RLHF pairs

Supported row shape:

```json
{"prompt":"Write a polite refusal","chosen":"I can’t help with that, but...","rejected":"No."}
```

The skill checks chosen versus rejected equality, repeated prompts with conflicting labels, and length bias. It surfaces manual review samples because deterministic scripts cannot prove chosen is better.

## Classification fine-tunes

Supported row shape:

```json
{"text":"The product arrived broken","label":"negative"}
```

CSV and TSV inputs with `text` and `label` columns are also supported. Use `declared_labels` in config to catch labels outside an expected set.

## Raw text

One document per line:

```text
A short training document.
Another document.
```

Raw text is rare for fine-tuning but supported for length, duplicate, encoding, and PII checks.
