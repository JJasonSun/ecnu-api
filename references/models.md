# Model and account pointers

Keep the user's working model unless they need selection help. For a new
ordinary text task, `ecnu-plus` is the local starting default; consider
`ecnu-max` for more demanding tasks. This is a practical starting point, not
a measured quality or latency ranking.

## Find the current answer

| Question | Source |
|---|---|
| Supported model IDs, aliases, vision, context, underlying models | [Official model page](https://developer.ecnu.edu.cn/vitepress/llm/model.html) |
| Thinking switch and protocol-specific effort | [Thinking](https://developer.ecnu.edu.cn/vitepress/llm/thinking.html), then the chosen [endpoint](api_reference.md) |
| Token prices, fixed request costs, shared allowances, quota windows | [Current quota and pricing page](https://developer.ecnu.edu.cn/vitepress/llm/limit.html) |
| Obtain/configure credentials | [Authorization](https://developer.ecnu.edu.cn/vitepress/llm/authorization.html) |
| Residency, fallback, submitted data, retention, contractual requirements | [Data security](https://developer.ecnu.edu.cn/vitepress/llm/security.html) and [developer agreement](https://developer.ecnu.edu.cn/vitepress/llm/tos.html) |
| What changed and when | [Release notes](https://developer.ecnu.edu.cn/vitepress/llm/release.html) |
| Is there a reported incident? | [Service status](https://chat.ecnu.edu.cn/status) |

## Select the capability, not just a new model name

The [2026-09-30 release](https://developer.ecnu.edu.cn/vitepress/llm/release.html)
added multimodal retrieval and image editing. Contract checked 2026-10-02;
these are documented capabilities, not new live-test results.

| Model | Backend in the current model page | Integration choice |
|---|---|---|
| `ecnu-embedding-small` | bge-m3 | Keep for existing text-only, 1024-dimensional indexes |
| `ecnu-embedding-vl` | Qwen3-VL-Embedding-8B | Text, one image per item, or both; default 4096 dimensions, optional 1024/2048/4096 |
| `ecnu-rerank` | bge-reranker-v2-m3 | Text query and text candidates |
| `ecnu-rerank-vl` | Qwen3-VL-Reranker-8B | Text/image query and candidates; rerank an already retrieved candidate set |
| `ecnu-image` | qwen-image-2.1 | Generate from text or edit one existing image; different request formats and prompt handling |

Use the [retrieval and image recipes](examples.md) for the differences that
affect requests. Equal vector dimensions do not imply compatible embedding
spaces: changing embedding models requires re-embedding the indexed items and
using that same model and dimensions for queries. A reranker can change without
replacing stored vectors; its relevance scores are not scientific or educational
quality judgments and should not be compared across models.

For image understanding, the current model page specifies `ecnu-plus`.
`ecnu-max` currently uses DeepSeek-V4-Flash-0731 and is text-only; older
DeepSeek-V4.1 and successful vision observations are historical, not current
capability guarantees. Keep stable ECNU aliases in requests and recheck backend
labels before displaying them. Do not relabel old generated assets as output
from a newly announced backend.

## ECNU-specific boundaries

Use primary ECNU model names for new integrations rather than upstream names
or historical aliases. A response's `model` metadata need not echo the requested
name. `/models` is runtime visibility, not a capability or authentication test.

Upstream model cards can explain model design, but do not establish ECNU's
request fields, thinking defaults, context units, output limits, performance,
or deployment path. Do not copy upstream serving flags into requests.

For a cost calculation, fetch current prices and show the input/output and
cache assumptions. Do not assume a cache-hit ratio or treat estimated usage as
verified account debit. A code-only task does not require a cost calculation.

If current documentation is unavailable, do not invent current account values.
Continue independent implementation work with the relevant local recipe,
identify the unverified decision, and defer only what depends on that value.

Historical model/Agent discussion remains in
[agent_development.md](agent_development.md) to preserve references from past
observations. It is not required reading for an ordinary integration and is
not a current model benchmark.
