# ECNU Models, Credits, Quotas, and Errors

## Table of Contents

- [Source Precedence](#source-precedence)
- [Primary Dialog Models](#primary-dialog-models)
- [Compatibility Aliases](#compatibility-aliases)
- [Specialized Models](#specialized-models)
- [Deployment and Availability](#deployment-and-availability)
- [Thinking Mode](#thinking-mode)
- [Shared Credits Quotas](#shared-credits-quotas)
- [Dialog Credits Calculation](#dialog-credits-calculation)
- [Fixed-Cost Capabilities](#fixed-cost-capabilities)
- [Official Token Equivalents](#official-token-equivalents)
- [Errors](#errors)
- [Official Sources](#official-sources)

## Source Precedence

ECNU documentation pages are not always updated together. Resolve conflicts in
this order:

1. Use the current model page for model identity, context figures, aliases, and
   capabilities.
2. Use the endpoint page for JSON fields, field types, and endpoint-specific
   limits.
3. Use the quota page for current prices, cache treatment, and quota periods.
4. Use release notes to understand when a change occurred, not to override a
   newer current-state page.
5. Use `GET /models` for runtime discovery, while remembering that aliases and
   capabilities may require the documentation for interpretation.

Example: the vision endpoint page still names `ecnu-vl`, while the newer model
page says `ecnu-vl` is a compatibility alias for `ecnu-plus`. New integrations
should use `ecnu-plus`.

## Primary Dialog Models

| Model | Underlying model | Published context | Thinking | Tools | Vision | Positioning |
|---|---|---|---|---|---|---|
| `ecnu-max` | DeepSeek-V4-Flash | 1M | Supported, default off | Yes | No | Flagship for complex text and code tasks |
| `ecnu-plus` | Qwen3.6-27B | 256K | Supported, default off | Yes | Yes | General-purpose balance of quality, cost, and latency |

The model table labels the context only as `1M` and `256K`; it does not specify
tokens or characters. Preserve those figures without adding a unit. The
Anthropic compatibility page separately calls `ecnu-max[1m]` a 1M-character
context signal for Anthropic tools.

Use `ecnu-plus` for all new image-understanding integrations. `ecnu-max` no
longer supports vision after its DeepSeek-V4-Flash upgrade.

## Compatibility Aliases

Prefer `ecnu-max` and `ecnu-plus` for new integrations.

| Historical request model | Effective behavior | Note |
|---|---|---|
| `ecnu-reasoner` | `ecnu-max` plus thinking enabled | Thinking defaults on |
| `ecnu-reasoner-lite` | `ecnu-plus` plus thinking enabled | Thinking defaults on |
| `ecnu-turbo` | `ecnu-plus` | Legacy alias; still used in structured-output docs |
| `ecnu-vl` | `ecnu-plus` | Legacy vision alias |
| `InnoSpark` | `ecnu-plus` | Legacy alias |
| `educhat-r1` | `ecnu-plus` | Legacy alias |
| `educhat-general` | `ecnu-plus` | Legacy alias |
| `educhat-psychology` | `ecnu-plus` | Legacy alias |
| `ChatECNU` | `ecnu-plus` | Legacy alias |
| `gpt-4` | `ecnu-plus` | Compatibility name |

For Anthropic-compatible requests, mapping is broader:

| Anthropic request name | Effective model |
|---|---|
| `opus` family | `ecnu-max` |
| `sonnet` or `haiku` family | `ecnu-plus` |
| Other unrecognized names | `ecnu-plus` |

Use `ecnu-max[1m]` only with Anthropic tools that inspect the model name for
context capability. The compatibility layer strips the suffix before routing.

## Specialized Models

| Model | Underlying model | Request contract | Output or capability |
|---|---|---|---|
| `ecnu-embedding-small` | bge-m3 | `input` is one string or a string array; published limit 8192 characters with batch scope unspecified | 1024-float embeddings |
| `ecnu-rerank` | bge-reranker-v2-m3 | `documents` is `string[]`; each document at most 8192 characters | Ranked indices and relevance scores |
| `ecnu-image` | Z-Image-Turbo | Prompt at most 1024 characters; prompts over 500 may be compressed | Image URL or base64 |
| `ecnu-tts` | CosyVoice2-0.5B | Input at most 4096 characters | Binary audio |

The model page calls embedding and rerank context `8K`, while their endpoint
pages express limits in characters. Use the endpoint wording for request
validation; do not convert 8192 characters to 8192 tokens.

### TTS voices

| Voice | Description |
|---|---|
| `xiayu` | Balanced male voice; default |
| `liwa` | Balanced female voice |

Supported audio formats: `mp3` (default), `opus`, `aac`, `flac`, `wav`, `pcm`.

## Deployment and Availability

ECNU states that listed models are deployed on campus and requests normally
remain on campus servers. During upgrades, failures, or heavy load, ECNU may
temporarily use cloud models to preserve continuity.

ChatECNU, the Agent platform, and other campus-specific AI applications use
separate service clusters. Their behavior or availability is therefore not a
direct measurement of a personal API token's endpoint.

Check current availability at https://chat.ecnu.edu.cn/status. Avoid parallel
API calls; short bursts can still trigger service protection even though the
old minute-level quota was removed.

## Thinking Mode

All current dialog models support the `thinking` object:

```json
{"thinking":{"type":"enabled"}}
```

or:

```json
{"thinking":{"type":"disabled"}}
```

With the OpenAI Python SDK, pass the object through `extra_body`. A response may
include `reasoning_content`; callers must tolerate its absence.

## Shared Credits Quotas

Personal tokens share one credits pool across all models and capabilities.

| Period | Default quota |
|---|---|
| Every 5 hours | 2000 credits |
| Daily | 5000 credits |
| Monthly | 50000 credits |

Minute-level quota enforcement has been removed, but abnormal high-frequency
traffic can still trigger service protection. Production systems serving ECNU
users may receive independent quota pools. The official contact for higher
requirements is `dataservice@ecnu.edu.cn`.

## Dialog Credits Calculation

Dialog models distinguish cache-miss input, cache-hit input, and output or
thinking tokens. Cached input currently costs one fifth of uncached input.

| Model | Input miss | Input hit | Output/thinking |
|---|---|---|---|
| `ecnu-plus` | 100 credits / 1M tokens | 20 credits / 1M tokens | 400 credits / 1M tokens |
| `ecnu-max` | 300 credits / 1M tokens | 60 credits / 1M tokens | 1200 credits / 1M tokens |

Formulas:

```text
ecnu-plus = input_miss / 1M * 100
          + input_hit  / 1M * 20
          + output     / 1M * 400
```

```text
ecnu-max  = input_miss / 1M * 300
          + input_hit  / 1M * 60
          + output     / 1M * 1200
```

Do not calculate all input at the cache-miss rate when cache usage is known.
Do not promise a cache-hit ratio; ECNU uses 90% only for its published examples.

Official examples assuming a 90% input cache-hit rate:

| Request | `ecnu-plus` | `ecnu-max` |
|---|---|---|
| 1,500 input + 800 output | 0.36 credits | 1.09 credits |
| 10K input + 2K output | 1.08 credits | 3.24 credits |
| 100K input + 2K output | 3.6 credits | 10.8 credits |
| 500K input + 5K output | 16 credits | 48 credits |
| 1M input + 10K output | 32 credits | 96 credits |

## Fixed-Cost Capabilities

These calls are currently priced per call rather than per token:

| Capability | Model | Cost |
|---|---|---|
| Embedding | `ecnu-embedding-small` | 0.05 credits / call |
| Rerank | `ecnu-rerank` | 0.1 credits / call |
| Image generation | `ecnu-image` | 30 credits / successful generation |
| Text-to-speech | `ecnu-tts` | 5 credits / call |

The per-call price does not define a supported batch size. In particular, the
embedding docs allow a string array but publish no maximum item count or total
character rule. Do not maximize batches based only on billing.

## Official Token Equivalents

The quota page publishes these rough equivalents assuming 90% of input tokens
are cache hits. They are estimates, not guaranteed capacity.

| Quota | `ecnu-plus` input-only | `ecnu-plus` 4:1 mix | `ecnu-max` input-only | `ecnu-max` 4:1 mix |
|---|---|---|---|---|
| 2000 credits / 5h | ~71.43M input tokens | ~19.53M total tokens | ~23.81M input tokens | ~6.51M total tokens |
| 5000 credits / day | ~179M input tokens | ~48.83M total tokens | ~59.52M input tokens | ~16.28M total tokens |
| 50000 credits / month | ~1.786B input tokens | ~488M total tokens | ~595M input tokens | ~163M total tokens |

Input-heavy document, codebase, and RAG workloads may be closer to the
input-only estimate only when their cache behavior resembles the assumption.

## Errors

| Status | Meaning | Typical cause |
|---|---|---|
| `401` | Unauthorized | Token missing or invalid |
| `403` | Forbidden | Client IP is not in the third-party allowlist |
| `422` | Request validation failed | Required field missing, wrong JSON type, unsupported shape |
| `429` | Too many requests | Quota exhausted, rate control, or short-term service protection |

`detail` can be a string:

```json
{"detail":"无效的令牌"}
```

or an array of validation errors:

```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "model"],
      "msg": "Field required"
    }
  ]
}
```

For `422`, report the `loc`, `type`, and `msg` rather than reducing every error
to a generic invalid request. For `429`, stop concurrent retries and inspect
credits before applying backoff.

## Official Sources

- Models and aliases: https://developer.ecnu.edu.cn/vitepress/llm/model.html
- Quotas and prices: https://developer.ecnu.edu.cn/vitepress/llm/limit.html
- Errors: https://developer.ecnu.edu.cn/vitepress/llm/error.html
- Anthropic compatibility: https://developer.ecnu.edu.cn/vitepress/llm/api/anthropic.html
- Release notes: https://developer.ecnu.edu.cn/vitepress/llm/release.html
- Service status: https://chat.ecnu.edu.cn/status
