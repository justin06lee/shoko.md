# Common fine-tuning data pitfalls

Use this list to interpret report findings. Do not regurgitate it verbatim.

- **Train/test leakage via paraphrase:** exact leakage catches the obvious case, but near-duplicate leakage often reveals paraphrased validation examples. This inflates evals and hides overfitting.
- **Chosen/rejected flipped:** deterministic checks cannot prove preference quality, but equality, suspicious repeated prompts, and length bias are good smoke tests. Always manually review samples.
- **Role alternation broken by tool calls:** chat exports often interleave tool outputs incorrectly. Validate `tool_calls`, `tool_call_id`, and whether assistant turns are empty only because a tool call is present.
- **System prompt drift:** many unique system prompts may be intentional, but it often means metadata leaked into prompts or exports were merged from incompatible projects.
- **PII in usernames inside chat logs:** emails, phone numbers, street addresses, API keys, IPs, and names embedded in free text can silently enter training data.
- **Special-token contamination:** strings such as `<|endoftext|>` or `<|im_start|>` often mean the dataset was exported after tokenization or from model transcripts rather than source conversations.
- **CSV label normalization drift:** labels like `Positive`, `positive`, and ` positive` create avoidable class fragmentation.
- **Length-tail surprises:** a small number of huge records can dominate token budget, get truncated by a training API, or cause unexpected costs.
