# Models and account pointers

Keep the user's working model unless they need selection help. For a new
ordinary text task, `ecnu-plus` is the local starting default; consider
`ecnu-max` for more demanding tasks. This is a practical starting point, not
a measured quality or latency ranking.

## Account pages

| Question | Official page |
|---|---|
| Prices, peak hours, cache discount, 7-day quota, concurrency caps | [Quota and pricing](https://developer.ecnu.edu.cn/vitepress/llm/limit.html) |
| Creating and managing keys | [My token](https://developer.ecnu.edu.cn/vitepress/llm/authorization.html) |
| Residency, cloud fallback, use of submitted data | [Data security](https://developer.ecnu.edu.cn/vitepress/llm/security.html), [developer agreement](https://developer.ecnu.edu.cn/vitepress/llm/tos.html) |
| What changed and when | [Release notes](https://developer.ecnu.edu.cn/vitepress/llm/release.html) |
| Reported incidents | [Service status](https://chat.ecnu.edu.cn/status) (requires ECNU single sign-on) |

## Current model snapshot

Checked against the model page on 2026-11-23. Use it to choose, then recheck
the official page before displaying or depending on a value.

| Model | Backend | Use for |
|---|---|---|
| `ecnu-plus` | Qwen3.8-Flash-Next | General text, tools, image input, JSON; 256K context; effort `low` / `medium` / `xhigh` |
| `ecnu-max` | DeepSeek-V4.1-Flash-1017 | Harder text, code and image tasks; 512K context; effort `low` / `high` / `max` |
| `ecnu-embedding-small` | bge-m3 | Text-only, 1024-dimensional indexes |
| `ecnu-embedding-vl` | Qwen3-VL-Embedding-8B | Text, one image per item, or both; 4096 dimensions by default, 1024/2048 optional |
| `ecnu-rerank` | bge-reranker-v2-m3 | Text query and text candidates |
| `ecnu-rerank-vl` | Qwen3-VL-Reranker-8B | Text/image query and candidates |
| `ecnu-decision` | d3-flash | Classification, yes/no or ordered scoring over supplied material ([recipe](examples.md#structured-decision)) |
| `ecnu-image` | qwen-image-2.1 | Generate from text or edit one image ([recipe](examples.md#image-generation-and-editing)) |
| `ecnu-tts` | Fun-CosyVoice3-0.5B | Speech from up to 4096 characters, 16 voices |

Thinking is off by default on both chat models. Historical names such as
`ecnu-reasoner` (max with thinking on) and `ecnu-turbo` are compatibility
aliases; use the primary names in new code.

Equal vector dimensions do not imply compatible embedding spaces: changing
embedding models requires re-embedding the indexed items and querying with that
same model and dimension. A reranker can change without replacing stored
vectors; its scores are not comparable across models.

## ECNU-specific boundaries

A response's `model` field is a backend label and need not echo the requested
name. `/models` shows runtime visibility, not a capability, contract, or
authentication result.

Upstream model cards explain model design but do not establish ECNU's request
fields, thinking defaults, context units, output limits, performance, or
deployment path. Do not copy upstream serving flags into requests.

For thinking controls, follow the [current recipe](examples.md#thinking-and-tool-history);
for concurrency, peak pricing and caching, see [engineering](engineering.md).

For a cost calculation, fetch current prices and state the input/output, cache
and peak-hour assumptions. Estimated usage is not verified account debit. A
code-only task does not require a cost calculation.

If the official pages are unreachable, do not present this snapshot as freshly
verified. Continue independent implementation work and name the value that
could not be rechecked.
