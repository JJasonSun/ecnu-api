---
name: ecnu-api
description: >
  Integrate with the ECNU (East China Normal University) LLM Open Platform.
  Covers OpenAI-compatible Chat Completions and Responses APIs, multimodal
  input, embeddings, rerank, image generation, text-to-speech, structured
  output, model discovery, and the separate Anthropic-compatible API. Use when
  an AI agent needs to call or troubleshoot chat.ecnu.edu.cn APIs, select ECNU
  models, validate request types and limits, configure an OpenAI or Anthropic
  client, or explain authentication, credits, quotas, errors, and compatibility
  aliases. Triggers include "ECNU API", "ChatECNU", "华东师范大学 API",
  "ECNU 大模型", "ecnu-max", "ecnu-plus", "ecnu-embedding-small",
  "ecnu-rerank", "ecnu-image", and "ecnu-tts".
---

# ECNU LLM Open Platform API

Use the current ECNU developer documentation as the authority. Treat request
types, units, and URL roots as separate contracts; do not infer unsupported
OpenAI parameters merely because an endpoint is OpenAI-compatible.

## Choose the Correct Protocol Root

| Protocol | Base or full URL | Use for |
|---|---|---|
| OpenAI-compatible | `https://chat.ecnu.edu.cn/open/api/v1` | Chat Completions, Responses, embeddings, images, TTS, models |
| Anthropic-compatible | `https://chat.ecnu.edu.cn/open/api/anthropic` | Anthropic SDK and `/v1/messages` |
| Embed iFrame (experimental) | `https://chat.ecnu.edu.cn/open/api/embed/app` | One-time embedded ChatECNU URL |

Never append the Anthropic path to the OpenAI base. The full Anthropic messages
URL is `https://chat.ecnu.edu.cn/open/api/anthropic/v1/messages`.

Authenticate API calls with:

```http
Authorization: Bearer <your_api_key>
Content-Type: application/json
```

Obtain a key in ChatECNU under the avatar menu, "我的令牌". Never place a real
key in source, examples, logs, screenshots, or error reports. Tokens are
personal, default to a 90-day validity, and must be renewed before expiry.

## Endpoint Map

Paths below are relative to the OpenAI-compatible base unless a full URL is
shown.

| Capability | Method and path | Model |
|---|---|---|
| Chat Completions | `POST /chat/completions` | `ecnu-max`, `ecnu-plus` |
| Responses | `POST /responses` | `ecnu-max`, `ecnu-plus` |
| Vision | `POST /chat/completions` | Prefer `ecnu-plus`; `ecnu-vl` is a legacy alias |
| Embeddings | `POST /embeddings` | `ecnu-embedding-small` |
| Rerank | `POST /rerank` | `ecnu-rerank` |
| Image generation | `POST /images/generations` | `ecnu-image` |
| Text-to-speech | `POST /audio/speech` | `ecnu-tts` |
| Model list | `GET /models` | N/A |
| Structured output | `POST /chat/completions` | `ecnu-plus` and alias `ecnu-turbo` |
| Anthropic messages | `POST https://chat.ecnu.edu.cn/open/api/anthropic/v1/messages` | `ecnu-max`, `ecnu-plus`, mapped aliases |
| Embed iFrame | `POST https://chat.ecnu.edu.cn/open/api/embed/app` | N/A |

## Current Primary Models

| Model | Underlying model | Published context | Thinking | Tools | Vision |
|---|---|---|---|---|---|
| `ecnu-max` | DeepSeek-V4-Flash-0731 | 1M | Supported, default off | Yes | No |
| `ecnu-plus` | Qwen3.6-27B | 256K | Supported, default off | Yes | Yes |

The model page does not label the context figures as tokens or characters. Do
not add a unit. The Anthropic page separately describes `ecnu-max[1m]` as 1M
characters for Anthropic tools.

Prefer the model page over older endpoint examples when model names conflict.
The former vision page now redirects to the Chat Completions multimodal
section; use `ecnu-plus` for new image-understanding integrations and retain
`ecnu-vl` only for compatibility.

## Critical Request Contracts

### Embeddings

- Send `input` as one string or an array of strings: `string | string[]`.
- Do not send integer token arrays. ECNU uses a non-OpenAI tokenizer and the
  official docs explicitly warn that pre-tokenized OpenAI token IDs are not
  supported.
- The published input limit is 8192 characters. The docs do not say whether
  this applies to each array element or the whole array, and they publish no
  maximum batch size. State that ambiguity instead of inventing a limit.
- Output vectors contain 1024 floats. The direct API documents only `model` and
  `input`; do not present arbitrary dimensions as supported.
- For LangChain `OpenAIEmbeddings`, set `dimensions=1024` and
  `check_embedding_ctx_length=False`.

### Rerank

- Send `documents` as a string array and `query` as a string.
- Each document is limited to 8192 characters.
- `top_n` defaults to 5. The docs publish no maximum, no document-count limit,
  and no query-length limit. Do not fabricate them.
- `return_documents` controls whether document text is returned.

### Vision

- Use structured message content with `text` and `image_url` parts.
- `image_url.url` may be a public URL or a base64 data URL.
- The API page publishes no image-count or image-size limit. A ChatECNU UI
  release note about five uploaded images is not an API limit.

### Image and Audio

- Image prompt: at most 1024 characters. Prompts over 500 characters may be
  compressed. Supported sizes are documented in the API reference.
- Image URLs expire after 24 hours; transfer them immediately.
- TTS input: at most 4096 characters. Speed range: 0.25 through 4.0.

## Operational Rules

- Avoid parallel API calls. Wait for one response before starting the next to
  reduce service-protection failures.
- All capabilities share the credits quota. Dialog usage distinguishes cached
  and uncached input; cached input currently costs one fifth of uncached input.
- Enable dialog thinking with `{"thinking": {"type": "enabled"}}`. With the
  OpenAI Python SDK, pass this ECNU extension through `extra_body`.
- `ecnu-max` supports `reasoning_effort` (`low` / `high` / `max`) to control
  thinking intensity when thinking is enabled. `ecnu-plus` ignores this
  parameter. The Anthropic-compatible API uses `output_config.effort` and the
  Responses API uses `reasoning.effort`, both with a different set of levels
  mapped to `ecnu-max` tiers.
- When thinking is enabled, `temperature` and `top_p` may not take effect or
  may be restricted; prefer defaults.
- Outside thinking mode, the model page advises tuning `temperature`, `top_p`,
  and other sampling parameters per the underlying models' official
  documentation; it publishes no platform-specific defaults.
- Native `search_mode` web search was removed. Use tool calling or an external
  search implementation.
- Treat `422` as a request-shape/type failure and inspect `detail`; treat `429`
  as quota, rate, or short-term service protection.
- Check current availability at `https://chat.ecnu.edu.cn/status`.

## Read the Relevant Reference

- Read [references/api_reference.md](references/api_reference.md) for exact
  request fields, limits, response shapes, protocol roots, documented
  ambiguities, and the Live Verification Notes on observed docs-vs-service
  deviations.
- Read [references/models.md](references/models.md) for model aliases,
  deployment notes, current cached/uncached credit formulas, quotas, and errors.
- Read [references/examples.md](references/examples.md) for minimal Python and
  HTTP examples, including scalar and array embeddings, Responses API,
  Anthropic 1M context, sequential batching, and error handling.

When a production decision depends on a limit the reference marks as
undocumented, verify against the official page or a controlled authenticated
request. Do not turn an observation into a permanent platform guarantee.

## Official Documentation

- Models: https://developer.ecnu.edu.cn/vitepress/llm/model.html
- Thinking: https://developer.ecnu.edu.cn/vitepress/llm/thinking.html
- API index: https://developer.ecnu.edu.cn/vitepress/llm/api/models.html
- Responses: https://developer.ecnu.edu.cn/vitepress/llm/api/responses.html
- Quotas: https://developer.ecnu.edu.cn/vitepress/llm/limit.html
- Errors: https://developer.ecnu.edu.cn/vitepress/llm/error.html
- Release notes: https://developer.ecnu.edu.cn/vitepress/llm/release.html
- Local deployment and data security: https://developer.ecnu.edu.cn/vitepress/llm/security.html
- Developer agreement (token rules): https://developer.ecnu.edu.cn/vitepress/llm/tos.html
- Service status: https://chat.ecnu.edu.cn/status
