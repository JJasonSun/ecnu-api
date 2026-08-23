# ECNU Models, Credits, and Quotas

Verify time-sensitive values against the official model and quota pages before
a production decision.

## Source precedence

1. Current model page: identity, context figures, aliases, and capabilities.
2. Endpoint page: request fields, types, and endpoint-specific limits.
3. Quota page: current prices, cache treatment, and quota periods.
4. Release notes: change dates.
5. `GET /models`: runtime visibility only.

## Primary dialog models

| Model | Underlying model | Published context | Thinking | Tools | Vision |
|---|---|---|---|---|---|
| `ecnu-max` | DeepSeek-V4-Flash-0731 | 1M | Supported, default off | Yes | No |
| `ecnu-plus` | Qwen3.6-27B | 256K | Supported, default off | Yes | Yes |

The model table does not label `1M` and `256K` as tokens or characters. Preserve
the published figures without adding a unit. The Anthropic page separately
describes `ecnu-max[1m]` as a 1M-character compatibility signal.

Use `ecnu-plus` for image understanding. Use `ecnu-max` for complex text and
code where its higher cost and latency are justified.

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

| Period | Default quota |
|---|---|
| Every 5 hours | 2000 credits |
| Daily | 5000 credits |
| Monthly | 50000 credits |

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
