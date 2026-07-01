# Fine-tuning dataset QC report

Generated: 2026-07-01T20:09:26+00:00

## Header

| File | Record count | Detected format |
| --- | --- | --- |
| shoko-md/examples/classification.csv | 7 | classification |
| shoko-md/examples/preference.jsonl | 3 | preference_pair |
| shoko-md/examples/prompt_completion.jsonl | 3 | prompt_completion |
| shoko-md/examples/train.chat.jsonl | 7 | openai_chat |
| shoko-md/examples/val.chat.jsonl | 2 | openai_chat |

## Summary table

| Check | Severity | Finding |
| --- | --- | --- |
| split_leakage | CRITICAL | 1 exact cross-split leak(s); 1 near cross-split cluster(s) |
| chat_format | CRITICAL | role_alternation (1); empty_assistant_turn (1); bad_tool_calls_type (1) |
| preference_pairs | CRITICAL | chosen_equals_rejected (1) |
| prompt_completion | CRITICAL | empty_completion (1) |
| schema_validation | WARNING | empty_text (3); special_token (2) |
| exact_duplicates | WARNING | Found 1 exact duplicate record(s) |
| near_duplicates | WARNING | Found 2 near-duplicate cluster(s) |
| pii_scan | WARNING | Found 12 regex PII/secret hit(s) |
| classification | WARNING | label_normalization (1) |
| format_detection | OK | Detected formats for 5 file(s) |
| encoding_sanity | OK | Encoding sanity checks complete |
| length_distribution | OK | Length stats computed |

## Critical issues

### split_leakage
- **issue** in `shoko-md/examples/train.chat.jsonl, shoko-md/examples/val.chat.jsonl`: 1 exact cross-split leak(s); 1 near cross-split cluster(s)

### chat_format_check
- **role_alternation** in `shoko-md/examples/train.chat.jsonl` at `{'file': 'shoko-md/examples/train.chat.jsonl', 'index': 3, 'line': 4}`: Two assistant turns in a row
- **empty_assistant_turn** in `shoko-md/examples/train.chat.jsonl` at `{'file': 'shoko-md/examples/train.chat.jsonl', 'index': 4, 'line': 5}`: Empty assistant turn at messages[1]
- **bad_tool_calls_type** in `shoko-md/examples/train.chat.jsonl` at `{'file': 'shoko-md/examples/train.chat.jsonl', 'index': 6, 'line': 7}`: tool_calls must be a list

### preference_pair_check
- **chosen_equals_rejected** in `shoko-md/examples/preference.jsonl` at `{'file': 'shoko-md/examples/preference.jsonl', 'index': 0, 'line': 1}`: chosen and rejected are identical
  - Example: `{"chosen":"Gravity pulls objects toward each other.","prompt":"Explain gravity simply.","rejected":"Gravity pulls objects toward each other."}`

### prompt_completion_check
- **empty_completion** in `shoko-md/examples/prompt_completion.jsonl` at `{'file': 'shoko-md/examples/prompt_completion.jsonl', 'index': 1, 'line': 2}`: completion is empty
  - Example: `{"completion":"","prompt":"Translate dog to French"}`

## Warnings

### preference_pair_check
- **conflicting_prompt_pairs** in `shoko-md/examples/preference.jsonl` at `{'file': 'shoko-md/examples/preference.jsonl', 'index': 2, 'line': 3}`: Same prompt has conflicting chosen/rejected across rows

### prompt_completion_check
- **completion_copies_prompt** in `shoko-md/examples/prompt_completion.jsonl` at `{'file': 'shoko-md/examples/prompt_completion.jsonl', 'index': 0, 'line': 1}`: completion appears to copy prompt
  - Example: `{"completion":"Translate cat to French","prompt":"Translate cat to French"}`

### validate_schema
- **empty_text** in `shoko-md/examples/train.chat.jsonl` at `{'file': 'shoko-md/examples/train.chat.jsonl', 'index': 4, 'line': 5}`: messages[1].content is empty or whitespace-only
  - Example: `{"messages":[{"content":"Can you help me?","role":"user"},{"content":"","role":"assistant"}]}`
- **special_token** in `shoko-md/examples/train.chat.jsonl` at `{'file': 'shoko-md/examples/train.chat.jsonl', 'index': 5, 'line': 6}`: messages[0].content contains special token <|endoftext|>
  - Example: `{"messages":[{"content":"Why is this token here <|endoftext|>?","role":"user"},{"content":"It should probably be removed.","role":"assistant"}]}`
- **special_token** in `shoko-md/examples/train.chat.jsonl` at `{'file': 'shoko-md/examples/train.chat.jsonl', 'index': 5, 'line': 6}`: messages_joined contains special token <|endoftext|>
  - Example: `{"messages":[{"content":"Why is this token here <|endoftext|>?","role":"user"},{"content":"It should probably be removed.","role":"assistant"}]}`
- **empty_text** in `shoko-md/examples/train.chat.jsonl` at `{'file': 'shoko-md/examples/train.chat.jsonl', 'index': 6, 'line': 7}`: messages[1].content is empty or whitespace-only
  - Example: `{"messages":[{"content":"Call a weather tool.","role":"user"},{"content":"","role":"assistant","tool_calls":{"name":"weather"}}]}`
- **empty_text** in `shoko-md/examples/prompt_completion.jsonl` at `{'file': 'shoko-md/examples/prompt_completion.jsonl', 'index': 1, 'line': 2}`: completion is empty or whitespace-only
  - Example: `{"completion":"","prompt":"Translate dog to French"}`

### dedup_exact
- **issue** in `shoko-md/examples/train.chat.jsonl`: 1 exact duplicate record(s)
  - Example: `[{"duplicate":{"file":"shoko-md/examples/train.chat.jsonl","index":1,"line":2},"first":{"file":"shoko-md/examples/train.chat.jsonl","index":0,"line":1},"hash":"01be6d83104ef3ec5e6dd52df63c37024f54316f698141c4fffe36439599bca6","sample":"{\"messages\":[{\"content\":\"You are a helpful support assistant.\",\"role\":\"system\"},{\"content\":\"My email is [REDACTED_EMAIL] and my address is [REDACTED_STREET_ADDRESS]. How do I reset my password?\",\"role\":\"user\"},{\"content\":\"Use the reset link in account settings.\",\"role\":\"assistant\"}]}"}]`

### dedup_near
- **issue** in `shoko-md/examples/train.chat.jsonl`: 1 near-duplicate cluster(s) at threshold 0.85
  - Example: `[{"members":[{"input_excerpt":"system: You are a helpful support assistant.\nuser: My email is [REDACTED_EMAIL] and my address is [REDACTED_STREET_ADDRESS]. How do I reset my password?\nassistant: Use the reset link in account settings.","loc":{"file":"shoko-md/examples/train.chat.jsonl","index":0,"line":1}},{"input_excerpt":"system: You are a helpful support assistant.\nuser: My email is [REDACTED_EMAIL] and my address is [REDACTED_STREET_ADDRESS]. How do I reset my password?\nassistant: Use the reset link in account settings.","loc":{"file":"shoko-md/examples/train.chat.jsonl","index":1,"line":2}}],"size":2}]`
- **issue** in `shoko-md/examples/preference.jsonl`: 1 near-duplicate cluster(s) at threshold 0.85
  - Example: `[{"members":[{"input_excerpt":"Write a friendly greeting.","loc":{"file":"shoko-md/examples/preference.jsonl","index":1,"line":2}},{"input_excerpt":"Write a friendly greeting.","loc":{"file":"shoko-md/examples/preference.jsonl","index":2,"line":3}}],"size":2}]`

### pii_scan
- **issue** in `shoko-md/examples/train.chat.jsonl`: Potential PII/secrets found by regex scan
  - Example: `{"email":[{"loc":{"file":"shoko-md/examples/train.chat.jsonl","index":0,"line":1},"match_count":2,"sample":"messages[0].content: You are a helpful support assistant.\nmessages[1].content: My email is [REDACTED_EMAIL] and my address is [REDACTED_STREET_ADDRESS]. How do I reset my password?\nmessages[2].content: Use the reset link in account settings.\nmessages_joined: system: You are a helpful support assistant.\nuser: My email is [REDACTED_EMAIL] and my address is [REDACTED_STREET_ADDRESS]. How do I reset my password?\nassistant: Use the reset link in account settings."},{"loc":{"file":"shoko-md/examples/train.chat.jsonl","index":1,"line":2},"match_count":2,"sample":"messages[0].content: You...`
- **issue** in `shoko-md/examples/val.chat.jsonl`: Potential PII/secrets found by regex scan
  - Example: `{"email":[{"loc":{"file":"shoko-md/examples/val.chat.jsonl","index":0,"line":1},"match_count":2,"sample":"messages[0].content: You are a helpful support assistant.\nmessages[1].content: My email is [REDACTED_EMAIL] and my address is [REDACTED_STREET_ADDRESS]. How do I reset my password?\nmessages[2].content: Use the reset link in account settings.\nmessages_joined: system: You are a helpful support assistant.\nuser: My email is [REDACTED_EMAIL] and my address is [REDACTED_STREET_ADDRESS]. How do I reset my password?\nassistant: Use the reset link in account settings."}],"street_address":[{"loc":{"file":"shoko-md/examples/val.chat.jsonl","index":0,"line":1},"match_count":2,"sample":"messages[...`

### classification_check
- **label_normalization** in `shoko-md/examples/classification.csv`: Labels differ only by case/whitespace
  - Example: `[{"normalized":"positive","variants":{"Positive":1,"positive":4}}]`

## Stats appendix

### Split leakage
Split counts: `{'train': 7, 'val': 2}`
Exact leakage count: `1`
Near leakage clusters: `1` using `fallback_pairwise_jaccard_no_datasketch`
Exact leakage examples: `[{"hash":"01be6d83104ef3ec5e6dd52df63c37024f54316f698141c4fffe36439599bca6","loc_a":{"file":"shoko-md/examples/train.chat.jsonl","index":1,"line":2},"loc_b":{"file":"shoko-md/examples/val.chat.jsonl","index":0,"line":1},"sample":"{\"messages\":[{\"content\":\"You are a helpful support assistant.\",\"role\":\"system\"},{\"content\":\"My email is [REDACTED_EMAIL] and my address is [REDACTED_STREET_ADDRESS]. How do I reset my password?\",\"role\":\"user\"},{\"content\":\"Use the reset link in account settings.\",\"role\":\"assistant\"}]}","split_a":"train","split_b":"val"}]`
Near leakage examples: `[{"members":[{"input_excerpt":"system: You are a helpful support assistant.\nuser: My email is [REDACTED_EMAIL] and my address is [REDACTED_STREET_ADDRESS]. How do I reset my password?\nassistant: Use the reset link in account settings.","loc":{"file":"shoko-md/examples/train.chat.jsonl","index":0,"line":1},"split":"train"},{"input_excerpt":"system: You are a helpful support assistant.\nuser: My email is [REDACTED_EMAIL] and my address is [REDACTED_STREET_ADDRESS]. How do I reset my password?\nassistant: Use the reset link in account settings.","loc":{"file":"shoko-md/examples/train.chat.jsonl","index":1,"line":2},"split":"train"},{"input_excerpt":"system: You are a helpful support assistant.\nuser: My email is [REDACTED_EMAIL] and my address is [REDACTED_STREET_ADDRESS]. How do I reset my password?\nassistant: Use the reset link in account settings.","loc":{"file":"shoko-md/examples/val.chat.jsonl","index":0,"line":1},"split":"val"}],"size":3,"splits":["train","val"]}]`

### Chat system prompt consistency
**shoko-md/examples/train.chat.jsonl**: 2 unique system prompt(s).
- 4 row(s): ``
- 3 row(s): `You are a helpful support assistant.`

**shoko-md/examples/val.chat.jsonl**: 1 unique system prompt(s).
- 2 row(s): `You are a helpful support assistant.`

### PII/secrets regex counts
**shoko-md/examples/train.chat.jsonl**
| Pattern | Count |
| --- | --- |
| email | 4 |
| street_address | 4 |
Samples in this report are redacted. Regex coverage is language- and US-biased; higher-recall PII review needs a dedicated PII tool.

**shoko-md/examples/val.chat.jsonl**
| Pattern | Count |
| --- | --- |
| email | 2 |
| street_address | 2 |
Samples in this report are redacted. Regex coverage is language- and US-biased; higher-recall PII review needs a dedicated PII tool.

### Classification label balance
**shoko-md/examples/classification.csv**
| Label | Count |
| --- | --- |
|  negative | 1 |
| Positive | 1 |
| neutral | 1 |
| positive | 4 |
Majority/minority ratio: `4.0`

### Length distributions
**shoko-md/examples/train.chat.jsonl**
- Tokenizer: `chars_div_4_heuristic` (approximate)
- Tokens: p50=55, p90=111.0, p99=111.0, max=111
- Characters: p50=219, p90=442.0, p99=442.0, max=442
```text
     28-36      | ############################## 2
     36-44      |  0
     44-52      |  0
     52-61      | ############################## 2
     61-69      |  0
     69-77      |  0
     77-86      |  0
     86-94      | ############### 1
     94-102     |  0
    102-111     | ############################## 2
```

**shoko-md/examples/classification.csv**
- Tokenizer: `chars_div_4_heuristic` (approximate)
- Tokens: p50=9, p90=10.4, p99=10.940000000000001, max=11
- Characters: p50=35, p90=40.6, p99=42.760000000000005, max=43
```text
      7-8       | ####### 1
      8-9       |  0
      9-10      | ############################## 4
     10-11      | ############### 2
```

**shoko-md/examples/preference.jsonl**
- Tokenizer: `chars_div_4_heuristic` (approximate)
- Tokens: p50=56, p90=56.8, p99=56.98, max=57
- Characters: p50=221, p90=226.6, p99=227.86, max=228
```text
     33-35      | ############### 1
     35-37      |  0
     37-40      |  0
     40-42      |  0
     42-45      |  0
     45-47      |  0
     47-49      |  0
     49-52      |  0
     52-54      |  0
     54-57      | ############################## 2
```

**shoko-md/examples/prompt_completion.jsonl**
- Tokenizer: `chars_div_4_heuristic` (approximate)
- Tokens: p50=13, p90=16.2, p99=16.92, max=17
- Characters: p50=51, p90=63.8, p99=66.68, max=67
```text
     11-12      | ############################## 1
     12-13      |  0
     13-14      | ############################## 1
     14-15      |  0
     15-16      |  0
     16-17      | ############################## 1
```

**shoko-md/examples/val.chat.jsonl**
- Tokenizer: `chars_div_4_heuristic` (approximate)
- Tokens: p50=99.5, p90=108.7, p99=110.77, max=111
- Characters: p50=396.0, p90=432.8, p99=441.08, max=442
```text
     88-90      | ############################## 1
     90-92      |  0
     92-94      |  0
     94-97      |  0
     97-99      |  0
     99-101     |  0
    101-104     |  0
    104-106     |  0
    106-108     |  0
    108-111     | ############################## 1
```

## Suggested next actions

1. Fix **split_leakage** first: 1 exact cross-split leak(s); 1 near cross-split cluster(s)
2. Fix **chat_format** first: role_alternation (1); empty_assistant_turn (1); bad_tool_calls_type (1)
3. Fix **preference_pairs** first: chosen_equals_rejected (1)
4. Fix **prompt_completion** first: empty_completion (1)
5. Then address **schema_validation**: empty_text (3); special_token (2)
6. Then address **pii_scan**: Found 12 regex PII/secret hit(s)
7. Then address **exact_duplicates**: Found 1 exact duplicate record(s)
8. Then address **classification**: label_normalization (1)
9. Then address **near_duplicates**: Found 2 near-duplicate cluster(s)
10. Manually inspect 20-50 random records before training; deterministic QC catches structural bugs, not response quality or factual correctness.

## Scope notes

- This report is deterministic QC only. It does not modify/clean data, judge answer quality, detect prompt injection, validate factual correctness, or replace human sampling.
- Prompt-completion semantic alignment and ML-based PII detection are intentionally out of scope.
