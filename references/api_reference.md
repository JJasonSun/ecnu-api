# ECNU API Reference

This file contains documented request contracts. Point-in-time service
differences belong in [known_deviations.md](known_deviations.md), not here.

## Protocol roots and authentication

### OpenAI-compatible APIs

```text
https://chat.ecnu.edu.cn/open/api/v1
```

Use this base for Chat Completions, Responses, embeddings, rerank, images, TTS,
and models.

### Anthropic-compatible API

```text
Base: https://chat.ecnu.edu.cn/open/api/anthropic
Messages: https://chat.ecnu.edu.cn/open/api/anthropic/v1/messages
```

### Embed iFrame

```text
https://chat.ecnu.edu.cn/open/api/embed/app
```

### Authentication

```http
Authorization: Bearer <ECNU_API_KEY>
Content-Type: application/json
```

Use environment variables. Tokens are personal and the developer agreement
states that their default validity is 90 days.

## Endpoint map

| Capability | Method and path | Model |
|---|---|---|
| Chat Completions | `POST /chat/completions` | `ecnu-max`, `ecnu-plus` |
| Responses | `POST /responses` | `ecnu-max`, `ecnu-plus` |
| Vision | `POST /chat/completions` | `ecnu-plus` |
| Embeddings | `POST /embeddings` | `ecnu-embedding-small` |
| Rerank | `POST /rerank` | `ecnu-rerank` |
| Image generation | `POST /images/generations` | `ecnu-image` |
| Text-to-speech | `POST /audio/speech` | `ecnu-tts` |
| Model list | `GET /models` | N/A |
| Structured output | `POST /chat/completions` | `ecnu-plus`, `ecnu-turbo` |
| Anthropic messages | full URL above | dialog models and mappings |
| Embed iFrame | full URL above | N/A |

## Chat Completions

```http
POST https://chat.ecnu.edu.cn/open/api/v1/chat/completions
```

Documented request fields include:

| Field | Type | Notes |
|---|---|---|
| `model` | string | Prefer `ecnu-max` or `ecnu-plus` |
| `messages` | array | Ordered messages |
| `messages[].role` | string | `system`, `user`, or `assistant` |
| `messages[].content` | string or array | Array form is used for vision |
| `stream` | boolean | Streams SSE when true |
| `temperature` | number | 0 through 1 |
| `top_p` | number | 0 through 1 |
| `tools` | array | OpenAI-compatible function definitions |
| `thinking` | object | `{"type":"enabled"}` or `{"type":"disabled"}` |
| `reasoning_effort` | string | `low`, `high`, or `max`; `ecnu-max` only |
| `response_format` | object | Structured output |
| `max_tokens` | integer | Use enough room for complete output |

Pass ECNU-specific fields through `extra_body` when using the OpenAI Python
SDK.

`reasoning_effort` only applies when thinking is enabled and only to
`ecnu-max`. `ecnu-plus` ignores it. Sampling controls may not take effect or
may be restricted in thinking mode.

If a tool was called during a thinking-mode conversation, retain the returned
`reasoning_content` in subsequent turns when required by the model. Do not
expose hidden reasoning to end users merely because a response field exists.

A non-streaming response follows the OpenAI completion-list shape with
`choices[].message`, `finish_reason`, and `usage`. For streaming, parse SSE
`data:` lines and stop at `[DONE]`.

Native `search_mode` web search was removed. Implement search through tool
calling or an external search service.

## Responses API

```http
POST https://chat.ecnu.edu.cn/open/api/v1/responses
```

Both primary dialog models support the Responses wire format. The ECNU page
does not publish a complete ECNU-specific field and event matrix. Start with
text input and verify advanced OpenAI Responses tools or event types before
depending on them.

For `ecnu-max`, `reasoning.effort` controls thinking intensity. The compatibility
layer maps its levels to ECNU tiers; `none` disables thinking.

## Vision

Use Chat Completions with `ecnu-plus`:

```json
{
  "model": "ecnu-plus",
  "messages": [
    {
      "role": "user",
      "content": [
        {"type": "text", "text": "Describe this image."},
        {
          "type": "image_url",
          "image_url": {"url": "data:image/jpeg;base64,<base64-data>"}
        }
      ]
    }
  ]
}
```

`image_url.url` may be a public URL or a base64 data URL. The API page does not
publish a maximum image count, byte size, pixel size, or MIME-type matrix.
Do not reuse a web-UI upload limit as an API contract.

## Embeddings

```http
POST https://chat.ecnu.edu.cn/open/api/v1/embeddings
```

| Field | Type | Required | Contract |
|---|---|---|---|
| `model` | string | Yes | `ecnu-embedding-small` |
| `input` | string or string[] | Yes | Raw text only |

Unsupported forms include integer token IDs and arrays of integer token arrays.
ECNU uses a non-OpenAI tokenizer.

The published input limit is 8192 characters, but the page does not specify
whether an array is checked per item, by combined length, or both. It publishes
no maximum batch item count.

The output contains 1024 floating-point values per embedding. The direct
request contract does not document a dimension-selection field. With LangChain,
disable automatic token-length conversion and validate output length after the
response.

## Rerank

```http
POST https://chat.ecnu.edu.cn/open/api/v1/rerank
```

The request is Cohere-compatible rather than part of the OpenAI SDK surface.

| Field | Type | Required | Contract |
|---|---|---|---|
| `model` | string | Yes | `ecnu-rerank` |
| `documents` | string[] | Yes | Each document at most 8192 characters |
| `query` | string | Yes | Search query |
| `return_documents` | boolean | No | Include document text |
| `top_n` | integer | No | Defaults to 5 |

No maximum document count, maximum `top_n`, or query-length limit is published.

## Image generation

```http
POST https://chat.ecnu.edu.cn/open/api/v1/images/generations
```

| Field | Type | Required | Contract |
|---|---|---|---|
| `model` | string | Yes | `ecnu-image` |
| `prompt` | string | Yes | At most 1024 characters |
| `size` | string | No | Defaults to `512x512` |
| `response_format` | string | No | `url` or `b64_json` |

Documented sizes:

```text
512x512
768x768
720x1280
1280x720
1024x1024
```

Prompts over 500 characters may be compressed. URL results are retained for 24
hours, so transfer them promptly. Treat retries after ambiguous failures as
potential duplicate charges.

## Text-to-speech

```http
POST https://chat.ecnu.edu.cn/open/api/v1/audio/speech
```

| Field | Type | Required | Contract |
|---|---|---|---|
| `model` | string | Yes | `ecnu-tts` |
| `input` | string | Yes | At most 4096 characters |
| `voice` | string | No | Defaults to `xiayu` |
| `response_format` | string | No | `mp3`, `opus`, `aac`, `flac`, `wav`, `pcm` |
| `speed` | number | No | 0.25 through 4.0 |

The success body is binary audio with a format-specific content type. Do not
parse it as JSON. The official docs and model page may not list voices in the
same place or at the same update time; consult the current TTS page before
validating a voice ID.

"Batch TTS" examples are sequential client loops, not one batch request.

## Model list

```http
GET https://chat.ecnu.edu.cn/open/api/v1/models
```

The documented response is an OpenAI-style list with `data[].id`, `object`,
`created`, and `owned_by`. Use it for runtime visibility, then consult the model
documentation for capabilities, aliases, and prices. Do not treat visibility
alone as a capability guarantee or an authentication check.

## Structured output

Structured output is documented for `ecnu-plus` and the legacy alias
`ecnu-turbo`.

```json
{
  "response_format": {
    "type": "json_schema",
    "json_schema": {
      "name": "result",
      "schema": {
        "type": "object",
        "properties": {
          "name": {"type": "string"}
        },
        "required": ["name"]
      }
    }
  }
}
```

XGrammar constrains structure, not factual or semantic correctness. Give clear
instructions and allocate enough `max_tokens` to complete every required field.

## Anthropic-compatible messages

Set:

```text
ANTHROPIC_BASE_URL=https://chat.ecnu.edu.cn/open/api/anthropic
ANTHROPIC_AUTH_TOKEN=<ECNU_API_KEY>
```

Documented mappings:

| Requested name | Effective model |
|---|---|
| `ecnu-max` | `ecnu-max` |
| `ecnu-plus` | `ecnu-plus` |
| `opus` family | `ecnu-max` |
| `sonnet` or `haiku` family | `ecnu-plus` |
| other unrecognized names | `ecnu-plus` |

The documentation describes `ecnu-max[1m]` for Anthropic tools that inspect the
model name to advertise a 1M-character context. Treat the suffix as
compatibility metadata, not a model name for OpenAI-compatible endpoints.

`output_config.effort` controls thinking intensity for `ecnu-max`; `none`
disables thinking. `ecnu-plus` ignores this field.

## Embed iFrame

```http
POST https://chat.ecnu.edu.cn/open/api/embed/app
```

The documented request uses `client_id`, `client_secret`, `userid`,
`username`, and `appid`. Returned tickets and URLs are credentials. Do not log
or persist them. Tickets are one-time use and expire.

## Errors and undocumented limits

| Status | Typical meaning |
|---|---|
| `401` | Missing or invalid credentials |
| `403` | Application or client IP is not authorized |
| `422` | Request body validation failed |
| `429` | Quota, rate control, or short-term service protection |
| `5xx` | Server, proxy, or undocumented compatibility failure |

`detail` may be a string or an array of validation objects. Preserve the HTTP
status, content type, and a bounded redacted body sample. Do not assume every
error is JSON.

When ECNU publishes no limit, say "not documented." Do not substitute an OpenAI
default, model-card value, UI limit, or one-time observation.

## Official sources

- https://developer.ecnu.edu.cn/vitepress/llm/model.html
- https://developer.ecnu.edu.cn/vitepress/llm/thinking.html
- https://developer.ecnu.edu.cn/vitepress/llm/api/models.html
- https://developer.ecnu.edu.cn/vitepress/llm/api/completions.html
- https://developer.ecnu.edu.cn/vitepress/llm/api/responses.html
- https://developer.ecnu.edu.cn/vitepress/llm/api/embedding.html
- https://developer.ecnu.edu.cn/vitepress/llm/api/rerank.html
- https://developer.ecnu.edu.cn/vitepress/llm/api/imagegenerate.html
- https://developer.ecnu.edu.cn/vitepress/llm/api/audio.html
- https://developer.ecnu.edu.cn/vitepress/llm/api/anthropic.html
- https://developer.ecnu.edu.cn/vitepress/llm/api/structuredoutput.html
- https://developer.ecnu.edu.cn/vitepress/llm/api/embediframe.html
- https://developer.ecnu.edu.cn/vitepress/llm/error.html
- https://developer.ecnu.edu.cn/vitepress/llm/tos.html
