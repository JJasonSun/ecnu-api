# ECNU Models, Credits, and Quotas

Model and quota documentation and upstream background were checked on 2026-09-06.
Verify time-sensitive values against the official model and quota pages before
a production decision. This check is not a live API test.

## Source precedence

1. Current model page: identity, context figures, aliases, and capabilities.
2. Endpoint page: request fields, types, and endpoint-specific limits.
3. Quota page: current prices, cache treatment, and quota periods.
4. Release notes: change dates.
5. `GET /models`: runtime visibility only.

Upstream model cards and papers explain model design and serving techniques;
they do not override ECNU's hosted request fields, defaults, limits, or prices.

## Primary dialog models

| Model | Underlying model | Published context | Thinking | Tools | Vision |
|---|---|---|---|---|---|
| `ecnu-max` | DeepSeek-V4-Flash-0731 | 1M | Supported, default off | Yes | No |
| `ecnu-plus` | Qwen3.8-27B | 256K | Supported, default off | Yes | Yes |

The model table does not label `1M` and `256K` as tokens or characters. Preserve
the published figures without adding a unit. The Anthropic page separately
describes `ecnu-max[1m]` as a 1M-character compatibility signal.

Use `ecnu-plus` for image understanding. Consider `ecnu-max` for complex text
and code when task quality justifies its higher token price; measure latency
on the deployed service rather than inferring it from the model name.

## Upstream model background

The following is **`upstream-background`**, not an ECNU API guarantee. Use it
for model selection and diagnosing differences from upstream examples.

### Qwen3.8-27B behind `ecnu-plus`

The [Qwen model card](https://huggingface.co/Qwen/Qwen3.8-27B), also
[linked by ECNU on ModelScope](https://modelscope.cn/models/Qwen/Qwen3.8-27B),
describes a 27B dense vision-language model with improved coding and
long-horizon agentic capabilities. These are Qwen's claims, not ECNU benchmarks.

| Upstream behavior | ECNU integration boundary |
|---|---|
| Native image and video understanding | ECNU documents image input on `ecnu-plus`, not a video request contract |
| 262,144-token native context, extendable to 1,000,000 through serving configuration such as YaRN | ECNU publishes 256K; do not enable a larger context by copying upstream flags |
| Thinking defaults on; effort defaults to `xhigh`, with `medium` and `low` also supported | ECNU defaults thinking off and ignores `reasoning_effort` on `ecnu-plus` |
| `preserve_thinking` defaults on to retain historical reasoning context | ECNU does not document this switch or `chat_template_kwargs`; preserve returned continuation fields only as required by the ECNU workflow |

Qwen recommends `temperature=1.0, top_p=0.95` for thinking and
`temperature=0.7, top_p=0.8` for non-thinking in its own serving examples.
These are tuning starting points, not ECNU defaults. Do not copy upstream
`top_k`, `min_p`, or other undocumented controls into ECNU requests; sampling
controls may be restricted in ECNU thinking mode.

### DeepSeek-V4-Flash-0731 behind `ecnu-max`

The [DeepSeek model card](https://huggingface.co/deepseek-ai/DeepSeek-V4-Flash-0731)
identifies 0731 as the official Flash release replacing the preview, with
enhanced agentic capabilities and an attached speculative-decoding module.
It is not V4-Pro; other DeepSeek models' capabilities do not establish vision
support for `ecnu-max`, which ECNU documents as text-only.

Upstream effort levels are `low`, `high`, and `max`. Keep ECNU's explicit
thinking switch and protocol-specific effort mappings below. DeepSeek's local
deployment advice uses `temperature=1.0`, with `top_p=0.95` for agent tasks
and `1.0` otherwise. Its 384K-token output-budget recommendation for high/max
is not an ECNU `max_tokens` limit or a suitable default for credit-bounded tests.

### DSpark inference acceleration

ECNU v3.3.0 announces DSpark support for `ecnu-max`. The
[DSpark paper](https://arxiv.org/abs/2607.05147) and
[DeepSeek's DeepSpec repository](https://github.com/deepseek-ai/DeepSpec)
describe speculative decoding: a lightweight draft module proposes token
blocks, and the target model verifies them, with confidence- and load-aware
verification scheduling. This is server-side decoding acceleration, not a
client-side instruction to reduce reasoning effort.

The 0731 model card configures DSpark through vLLM or SGLang server launch
options. ECNU documents no request-level DSpark switch, new model ID, or
numerical speed guarantee. Keep using `ecnu-max`; do not invent `dspark: true`.
Gains depend on draft acceptance, workload, hardware, and serving load. The
paper's DeepSeek-serving benchmarks are not measurements of ECNU. When latency
matters, compare time to first token and generation speed with matched prompts,
output lengths, thinking settings, and load under an authorized test budget.

## Compatibility aliases

Prefer the primary names for new integrations.

| Historical name | Effective behavior |
|---|---|
| `ecnu-reasoner` | `ecnu-max` with thinking enabled |
| `ecnu-reasoner-lite` | `ecnu-plus` with thinking enabled |
| `ecnu-turbo` | `ecnu-plus` |
| `ecnu-vl` | `ecnu-plus` |
| `InnoSpark` | `ecnu-plus` |
| `educhat-r1` | `ecnu-plus` |
| `educhat-general` | `ecnu-plus` |
| `educhat-psychology` | `ecnu-plus` |
| `ChatECNU` | `ecnu-plus` |
| `gpt-4` | `ecnu-plus` |

Anthropic mappings are broader: `opus` maps to `ecnu-max`; `sonnet` and `haiku`
map to `ecnu-plus`; other unrecognized names map to `ecnu-plus`.

These are internal compatibility-routing rules. The official Anthropic page
does not document whether the response `model` field echoes the requested alias
or identifies the effective ECNU model.

## Model identifiers in responses

A request model name selects a documented primary model or compatibility route;
it is not guaranteed to be echoed as the response label. Official Chat
Completions examples omit `model` in some responses and use a backend label in
others. Treat a returned `model` value as response metadata and do not require
equality with the requested name. The Anthropic response-label behavior is not
documented.

## Specialized models

| Model | Underlying model | Contract |
|---|---|---|
| `ecnu-embedding-small` | bge-m3 | Raw string or string array; documented input limit 8192 characters; 1024-float output |
| `ecnu-rerank` | bge-reranker-v2-m3 | String documents; 8192 characters per document |
| `ecnu-image` | Z-Image-Turbo | Prompt at most 1024 characters |
| `ecnu-tts` | Fun-CosyVoice3-0.5B | Input at most 4096 characters; 16 documented voices |

The model page labels embedding and rerank context as `8K`, while endpoint pages
express request limits in characters. Use the endpoint wording when validating
requests.

## Thinking mode

Enable or disable dialog thinking with:

```json
{"thinking":{"type":"enabled"}}
```

```json
{"thinking":{"type":"disabled"}}
```

For Chat Completions, `ecnu-max` accepts `reasoning_effort` values `low`, `high`,
or `max` when thinking is enabled. `ecnu-plus` ignores the field.

Anthropic-compatible requests use `output_config.effort`:

| Client value | `ecnu-max` tier |
|---|---|
| `minimal` | `low` |
| `low` | `low` |
| `medium` | `high` |
| `high` | `high` |
| `xhigh` | `high` |
| `max` | `max` |
| `none` | thinking disabled |

Responses-compatible requests use `reasoning.effort` with the same
compatibility mapping.

In tool-using multi-turn thinking conversations, preserve the assistant's
`reasoning_content` when the service requires it for continuation. Do not show
hidden reasoning to end users.

## Shared credits quotas

The current official quota page documents these defaults for personal tokens:

| Period | Shared default quota |
|---|---|
| Rolling 7 days | 20000 credits |

All of a user's personal tokens share this pool. Only consumption within the
last 7 days counts; this is not a calendar-week reset. The account owner can
manually reset the quota at any time from ChatECNU's left-side **开放平台**
entry, immediately restoring the full allowance. No quota-reset API is
documented. Do not automate a reset or treat it as authorization to increase
an application's approved spending ceiling.

Minute-level quota enforcement was reported as removed, but abnormal
high-frequency traffic may still trigger service protection. Recheck the quota
page before relying on these values.

## Dialog credits

Cached input is documented as costing one fifth of uncached input.

| Model | Input miss | Input hit | Output or thinking |
|---|---|---|---|
| `ecnu-plus` | 100 credits / 1M tokens | 20 / 1M | 400 / 1M |
| `ecnu-max` | 300 credits / 1M tokens | 60 / 1M | 1200 / 1M |

Do not assume a cache-hit ratio. ECNU's published examples use an assumption;
it is not a guarantee for an application.

## Fixed-cost capabilities

The current official quota page documents:

| Capability | Model | Cost |
|---|---|---|
| Embedding | `ecnu-embedding-small` | 0.05 credits / call |
| Rerank | `ecnu-rerank` | 0.1 credits / call |
| Image generation | `ecnu-image` | 30 credits / successful generation |
| Text-to-speech | `ecnu-tts` | 5 credits / call |

A per-call price does not define a supported batch size. Do not maximize a
batch based on billing alone.

## Deployment and data handling

The model page states that listed models are deployed locally and that data
processing normally occurs on campus servers. It also distinguishes
campus-specific applications such as ChatECNU and the Agent platform from
personal API service clusters.

The security page explicitly allows temporary cloud-model fallback during
model upgrades, failures, or excessive load. Do not promise that requests
never leave campus; confirm the deployment path when data residency matters.

The developer agreement makes the developer responsible for token protection,
lawful handling of personal information, downstream application behavior, and
rights to submitted inputs. It also states that de-identified input and output
may be used for service optimization, statistics, troubleshooting, and safety
risk control under the agreement's conditions.

Before sending personal, confidential, or regulated information, verify that
the intended use and data-handling basis are appropriate.

## Important changes

| Date | Change |
|---|---|
| 2026-08-31 | v3.3.0: Qwen3.8-27B for `ecnu-plus`; DSpark for `ecnu-max`; rolling 7-day 20000-credit quota and manual reset; dual-model structured-output fix; URL chat integration |
| 2026-08-10 | Reasoning-effort controls and compatibility mappings |
| 2026-08-09 | Security and developer-agreement documentation update |
| 2026-08-03 | TTS upgraded to Fun-CosyVoice3-0.5B; additional voices |
| 2026-08-01 | `ecnu-max` upgraded to DeepSeek-V4-Flash-0731 |
| 2026-04-24 | `ecnu-max` vision removal announced |
| 2026-04-03 | Dialog models consolidated to `ecnu-max` and `ecnu-plus` |
| 2025-03-20 | Native `search_mode` removed |

## Official sources

- https://developer.ecnu.edu.cn/vitepress/llm/model.html
- https://developer.ecnu.edu.cn/vitepress/llm/thinking.html
- https://developer.ecnu.edu.cn/vitepress/llm/limit.html
- https://developer.ecnu.edu.cn/vitepress/llm/release.html
- https://developer.ecnu.edu.cn/vitepress/llm/security.html
- https://developer.ecnu.edu.cn/vitepress/llm/tos.html
- https://chat.ecnu.edu.cn/status
