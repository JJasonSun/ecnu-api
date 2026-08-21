# ECNU API Reference

This reference separates documented facts from compatibility assumptions. A
field listed by the OpenAI or Anthropic API is not automatically supported by
ECNU; use only fields documented here or verified with the current service.

## Table of Contents

- [Protocol Roots and Authentication](#protocol-roots-and-authentication)
- [Chat Completions](#chat-completions)
- [Responses API](#responses-api)
- [Vision](#vision)
- [Embeddings](#embeddings)
- [Rerank](#rerank)
- [Image Generation](#image-generation)
- [Text-to-Speech](#text-to-speech)
- [Model List](#model-list)
- [Anthropic-Compatible API](#anthropic-compatible-api)
- [Structured Output](#structured-output)
- [Embed iFrame](#embed-iframe)
- [Errors and Undocumented Limits](#errors-and-undocumented-limits)
- [Live Verification Notes](#live-verification-notes)
- [Official Sources](#official-sources)

## Protocol Roots and Authentication

### OpenAI-compatible APIs

```text
https://chat.ecnu.edu.cn/open/api/v1
```

Use this base for `/chat/completions`, `/responses`, `/embeddings`, `/rerank`,
`/images/generations`, `/audio/speech`, and `/models`.

### Anthropic-compatible API

```text
Base: https://chat.ecnu.edu.cn/open/api/anthropic
Full messages URL: https://chat.ecnu.edu.cn/open/api/anthropic/v1/messages
```

This is a separate protocol root. Do not append `/anthropic/v1/messages` to the
OpenAI-compatible base.

### Embed iFrame API

```text
https://chat.ecnu.edu.cn/open/api/embed/app
```

This experimental endpoint is also outside the OpenAI-compatible `/v1` root.

### Authentication

```http
Authorization: Bearer <your_api_key>
Content-Type: application/json
```

Get the key from ChatECNU under the avatar menu, "我的令牌". A missing or
invalid token returns `401`. Some third-party applications also require an IP
allowlist; a mismatch returns `403`.

Per the developer agreement, tokens are personal (do not lend them to others or
expose them in browser or client code), default to a 90-day validity, and must
be renewed before expiry.

## Chat Completions

```http
POST https://chat.ecnu.edu.cn/open/api/v1/chat/completions
```

### Documented request fields

| Field | JSON type | Required | Contract |
|---|---|---|---|
| `model` | string | Yes | Prefer `ecnu-max` or `ecnu-plus` |
| `messages` | array | Yes | Ordered message objects |
| `messages[].role` | string | Yes | `system`, `user`, or `assistant` |
| `messages[].content` | string or array | Yes | String for text; structured parts for vision |
| `stream` | boolean | No | Return Server-Sent Events when true |
| `temperature` | number | No | 0 through 1; model-specific default; may be restricted when thinking is enabled |
| `top_p` | number | No | 0 through 1; model-specific default; may be restricted when thinking is enabled |
| `tools` | array | No | OpenAI-compatible function definitions |
| `tools[].type` | string | With tools | Fixed to `function` |
| `tools[].function.name` | string | With tools | Function name |
| `tools[].function.description` | string | With tools | Function description |
| `tools[].function.parameters` | object | With tools | JSON Schema-like parameters |
| `thinking` | object | No | ECNU extension: `{"type":"enabled"}` or `{"type":"disabled"}` |
| `reasoning_effort` | string | No | ECNU extension: `low`, `high`, or `max`; only `ecnu-max` with thinking enabled; `ecnu-plus` ignores it |
| `response_format` | object | No | Structured output; see below |
| `max_tokens` | integer | For bounded output | Used by ECNU's structured-output examples; publish no universal maximum |

`search_mode` remains visible in older request tables but native web search was
removed on 2025-03-20. Do not use it for new integrations.

When using the OpenAI Python SDK, pass `thinking` and `reasoning_effort` through
`extra_body` because they are ECNU extensions rather than standard SDK keywords:

```python
client.chat.completions.create(
    model="ecnu-max",
    messages=[{"role": "user", "content": "Analyze this."}],
    extra_body={
        "thinking": {"type": "enabled"},
        "reasoning_effort": "high",
    },
)
```

`reasoning_effort` only takes effect when `thinking` is set to `enabled` and
only applies to `ecnu-max`. When thinking is enabled, `temperature` and `top_p`
may not take effect or may be restricted; prefer defaults.

In multi-turn conversations under thinking mode, if the assistant called a
tool, its `reasoning_content` must be included in all subsequent turns; some
models return `400` if it is missing. If no tool was called, `reasoning_content`
can be omitted from subsequent context.

### Response fields

| Field | Meaning |
|---|---|
| `id` | Completion ID |
| `object` | Object type, normally `chat.completion` |
| `created` | Creation timestamp |
| `choices[].index` | Choice index |
| `choices[].message.role` | Assistant role |
| `choices[].message.content` | Final content |
| `choices[].message.reasoning_content` | Reasoning content when exposed |
| `choices[].message.tool_calls` | Requested function calls |
| `choices[].finish_reason` | Stop reason |
| `usage.prompt_tokens` | Estimated input usage |
| `usage.completion_tokens` | Estimated output usage |
| `usage.total_tokens` | Estimated total usage |

With `stream: true`, parse SSE `data:` lines and stop at `data: [DONE]`.

## Responses API

ECNU supports the OpenAI Responses wire format for both `ecnu-plus` and
`ecnu-max`.

```http
POST https://chat.ecnu.edu.cn/open/api/v1/responses
```

The official page currently documents the SDK form, model selection, and Codex
provider configuration, but does not publish a complete ECNU-specific field or
event table. Use the standard OpenAI client shape conservatively:

```python
response = client.responses.create(
    model="ecnu-max",
    input="Summarize this request.",
)
print(response.output_text)
```

Do not assume every OpenAI Responses tool or event type is implemented until it
is documented or verified. Requests use the same credits pool as other dialog
calls.

### Responses-API thinking effort

The Responses-compatible API supports `reasoning.effort` to control thinking
intensity for `ecnu-max`. Passing `reasoning.effort: "none"` disables thinking;
when omitted, the server default applies. The proxy applies the same tier
mapping as the Anthropic-compatible API.

## Vision

Vision uses the Chat Completions endpoint. Prefer `ecnu-plus`. The former
dedicated vision page now redirects to the completions page's multimodal
section, which documents `ecnu-plus` multimodal messages; the model page
defines `ecnu-vl` as a compatibility alias for `ecnu-plus`.

Use an array of content parts:

```json
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
```

Documented content-part types:

| Type | Required value |
|---|---|
| `text` | `text` string |
| `image_url` | `image_url.url`, as a public URL or base64 data URL |

The API page does not publish supported MIME types, byte limits, pixel limits,
or a maximum number of images. Do not reuse the ChatECNU web UI's five-upload
release note as an API contract.

## Embeddings

```http
POST https://chat.ecnu.edu.cn/open/api/v1/embeddings
```

### Request contract

| Field | JSON type | Required | Contract |
|---|---|---|---|
| `model` | string | Yes | Fixed to `ecnu-embedding-small` |
| `input` | string or string[] | Yes | One text or an array of texts |

Examples of valid input shapes:

```json
{"model":"ecnu-embedding-small","input":"one text"}
```

```json
{"model":"ecnu-embedding-small","input":["first text","second text"]}
```

Do not send either of these unsupported shapes:

```json
{"input":[123,456,789]}
```

```json
{"input":[[123,456],[789]]}
```

Those are OpenAI token-ID forms, not string arrays. ECNU's documentation
explicitly explains that OpenAI-tokenized integer input is incompatible with
the non-OpenAI embedding model.

### Limits and dimensions

- The official request table says `input` must not exceed 8192 characters.
- It does not state whether an array is limited per element, by total combined
  characters, or both.
- It does not publish a maximum array length or request byte size.
- The output is fixed at 1024 floating-point values.
- The direct request table documents no `dimensions` parameter. Do not request
  another size. The official LangChain example sets `dimensions=1024` only to
  describe the fixed output size to LangChain.

For production batching, validate that every item is a string, keep batches
conservative, submit sequentially, and split a batch if the service returns
`422`. Do not claim a guessed batch maximum as an ECNU limit.

### Response contract

The response follows the OpenAI list shape:

| Field | Meaning |
|---|---|
| `object` | `list` |
| `data[].object` | `embedding` |
| `data[].embedding` | 1024-float vector |
| `data[].index` | Position corresponding to the input array |
| `model` | `ecnu-embedding-small` |
| `usage.prompt_tokens` | Estimated input usage |
| `usage.total_tokens` | Estimated total usage |

For LangChain:

```python
OpenAIEmbeddings(
    base_url="https://chat.ecnu.edu.cn/open/api/v1",
    api_key=api_key,
    model="ecnu-embedding-small",
    dimensions=1024,
    check_embedding_ctx_length=False,
)
```

`check_embedding_ctx_length=False` prevents LangChain from converting strings
to OpenAI token IDs before sending them.

## Rerank

```http
POST https://chat.ecnu.edu.cn/open/api/v1/rerank
```

The request is Cohere-compatible, not part of the OpenAI SDK surface.

| Field | JSON type | Required | Contract |
|---|---|---|---|
| `model` | string | Yes | Fixed to `ecnu-rerank` |
| `documents` | string[] | Yes | Candidate documents; each at most 8192 characters |
| `query` | string | Yes | Search query |
| `return_documents` | boolean | No | Include document text in results |
| `top_n` | integer | No | Number returned; default 5 |

The official page publishes no maximum document count, maximum `top_n`, or
query-length limit. A caller should normally keep `top_n <= documents.length`,
but that is client-side logic, not a published ECNU constraint.

Response fields:

| Field | Meaning |
|---|---|
| `id` | Request ID |
| `results[].index` | Index into the submitted `documents` array |
| `results[].relevance_score` | Relevance score |
| `results[].document` | Document text when returned |

## Image Generation

```http
POST https://chat.ecnu.edu.cn/open/api/v1/images/generations
```

| Field | JSON type | Required | Contract |
|---|---|---|---|
| `model` | string | Yes | `ecnu-image` |
| `prompt` | string | Yes | At most 1024 characters; over 500 may be compressed |
| `size` | string | No | See supported values below; default `512x512` |
| `response_format` | string | No | `url` or `b64_json`; default `url` |

Supported sizes:

`512x512`, `768x768`, `720x1280`, `1280x720`, `1024x1024`

`data[].url` is retained for 24 hours only. `data[].b64_json` is returned for
base64 format. `data[].revised_prompt` may contain the service-adjusted prompt.
Generation failures can return `err_message` and a masked or revised prompt.

## Text-to-Speech

```http
POST https://chat.ecnu.edu.cn/open/api/v1/audio/speech
```

| Field | JSON type | Required | Contract |
|---|---|---|---|
| `model` | string | Yes | `ecnu-tts` |
| `input` | string | Yes | At most 4096 characters |
| `voice` | string | No | Voice ID from the voice list below; default `xiayu` |
| `response_format` | string | No | `mp3`, `opus`, `aac`, `flac`, `wav`, `pcm`; default `mp3` |
| `speed` | number | No | 0.25 through 4.0; default 1.0 |

The successful response body is binary audio with a format-specific MIME type.
The response includes a `Content-Disposition` header with a suggested filename.
When `response_format` is `pcm`, the response also includes `Content-Rate`
(sample rate), `Content-Channels` (fixed to 1), and `Content-Bits` (fixed to 16)
headers for direct playback.

### TTS voices

`ecnu-tts` supports 16 voice types. Dialect and character voices are trained on
specific corpora; test with short text before batch use.

**Campus (default)**

| Voice ID | Name | Description |
|---|---|---|
| `xiayu` | 夏雨 | Male, balanced (default) |
| `liwa` | 丽娃 | Female, balanced |

**Male**

| Voice ID | Name | Description |
|---|---|---|
| `male_warm` | 温润男声 | Gentle, restrained |
| `male_steady` | 稳重学长 | Young, steady, narrative |
| `male_news` | 男声·新闻 | Standard broadcast |
| `male_philosophy` | 男声·哲理 | Slower, reflective |
| `yunze` | 云泽大叔 | Middle-aged, deep |

**Female**

| Voice ID | Name | Description |
|---|---|---|
| `female_sweet` | 甜美女声 | Bright, sweet, friendly |
| `female_literary` | 女声·文艺 | Gentle, literary |
| `female_news` | 女声·新闻 | Standard broadcast, brisk |

**Dialect**

| Voice ID | Name | Description |
|---|---|---|
| `sichuan` | 四川话 | Sichuan dialect |
| `tianjin` | 天津话 | Tianjin dialect |
| `shaanxi` | 陕西话 | Shaanxi dialect |

**Multi-language and character**

| Voice ID | Name | Description |
|---|---|---|
| `japanese` | 日语 | Japanese voice |
| `lindaiyu` | 林黛玉 | Classical drama character |
| `labixiaoxin` | 蜡笔小新 | Anime character |

### TTS errors

Invalid parameters return `400` with a JSON body containing `error`,
`request_id`, and `details`:

```json
{
  "error": "voice 'xiaoming' not found",
  "request_id": "3f9a2b1c",
  "details": {
    "available_voices": ["xiayu", "liwa", "male_warm"]
  }
}
```

Common errors: `input is required`, `speed must be between 0.25 and 4.0`,
`response_format 'xxx' not supported`, `voice 'xxx' not found`. "Batch TTS" in
the official examples is a sequential client loop, not a batch request shape.

## Model List

```http
GET https://chat.ecnu.edu.cn/open/api/v1/models
```

There is no request body. Authentication is still required. The response is an
OpenAI-style list with `data[].id`, `object`, `created`, and `owned_by`. Treat
this endpoint as the runtime discovery surface; the example list in the docs
may lag the live service and may omit aliases or newer models.

## Anthropic-Compatible API

```text
ANTHROPIC_BASE_URL=https://chat.ecnu.edu.cn/open/api/anthropic
ANTHROPIC_AUTH_TOKEN=<your_api_key>
```

The Anthropic SDK sends messages to the resulting `/v1/messages` path.

### Model mapping

| Requested model | Effective ECNU model |
|---|---|
| `ecnu-max` | `ecnu-max` |
| `ecnu-plus` | `ecnu-plus` |
| `opus` family | `ecnu-max` |
| `sonnet` family | `ecnu-plus` |
| `haiku` family | `ecnu-plus` |
| Other unrecognized model names | `ecnu-plus` |

For Anthropic tools that inspect the model name to determine context size, pass
`ecnu-max[1m]`. The compatibility layer removes `[1m]` before routing and tells
the tool that the model supports the documented 1M-character context. Do not
generalize this suffix to the OpenAI-compatible APIs.

### Thinking effort

The Anthropic-compatible API supports `output_config.effort` to specify
thinking intensity. The proxy maps it to `ecnu-max` tiers:

| Client input (`output_config.effort`) | `ecnu-max` actual tier |
|---|---|
| `minimal` | `low` |
| `low` | `low` |
| `medium` | `high` |
| `high` | `high` |
| `xhigh` | `high` |
| `max` | `max` |
| `none` | Thinking disabled |

Thinking effort only applies to `ecnu-max`; `ecnu-plus` ignores it. Passing
`output_config.effort: "none"` disables thinking. When omitted, the server
default applies.

### Image handling in compatibility layers

When `ecnu-max` is called through the Anthropic or Responses compatibility
layer, the service automatically removes image content from the request to
avoid unsupported-vision errors. `ecnu-plus` retains image input normally. Do
not rely on this stripping for request validation; use `ecnu-plus` for all
image-understanding requests.

## Structured Output

Structured output is documented for `ecnu-plus` and its legacy alias
`ecnu-turbo`. It uses XGrammar constrained decoding through Chat Completions.

```json
{
  "response_format": {
    "type": "json_schema",
    "json_schema": {
      "name": "info_extraction",
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

Constraint decoding targets structural validity, not factual or semantic
correctness. Give explicit instructions and examples, include all required
fields in the schema, and allocate enough `max_tokens` for the complete value.

## Embed iFrame

```http
POST https://chat.ecnu.edu.cn/open/api/embed/app
```

This experimental integration supports JSON or URL-encoded form data. The
official page also describes an SSO-based embed mode for systems already
integrated with the campus identity service; no API is published for that
mode.

| Field | JSON type | Required | Meaning |
|---|---|---|---|
| `client_id` | string | Yes | Developer account ID |
| `client_secret` | string | Yes | Developer account secret |
| `userid` | string | Yes | User ID; docs suggest candidate/student ID where applicable |
| `username` | string | Yes | User display name |
| `appid` | string | Yes | Assigned embed application ID |

The response contains `code`, `message`, `data.ticket`, `data.url`, and
`data.expire` in seconds. A ticket is one-time use. Refresh the URL before
expiry; repeated access invalidates it. Treat `client_secret`, ticket, and URL
as credentials and do not log them.

## Errors and Undocumented Limits

| HTTP status | Meaning | Typical action |
|---|---|---|
| `401` | Missing or invalid token | Check bearer token handling |
| `403` | Client IP is not allowlisted | Check application/IP authorization |
| `422` | Request body validation failed | Inspect `detail`, field path, type, and shape |
| `429` | Quota, rate, or service protection | Stop parallel calls, inspect credits, retry later |

`detail` may be a string or an array of validation objects. Do not assume every
error response is JSON; retain the HTTP status and a bounded body sample.

When the docs publish no limit, write "not documented". Do not replace it with
an OpenAI default, a model-card limit, a UI limit, or a value observed once.

## Live Verification Notes

Observed on 2026-08-21 with a personal token against the live service. These
are point-in-time observations, not documented contracts; re-verify before
relying on them.

- `GET /models` does not return the documented `401` for a bad token. An
  invalid bearer token returns `200` with `{"object":"list","data":[]}`; a
  missing Authorization header returns `500` with an HTML error page inside
  the `error` field. Do not treat an empty model list as an auth check.
- The live `GET /models` list includes `ecnu-image-pro`, absent from the model
  page. A probe call to `/images/generations` with that model returned
  `500 Internal Server Error` as plain text, so it is listed but not
  verifiably usable yet.
- TTS with an invalid `voice` returned `500 Internal Server Error` as plain
  text, not the documented `400` JSON body with `details.available_voices`.
- TTS `pcm` responses set `Content-Type: audio/pcm` but did not include the
  documented `Content-Rate`, `Content-Channels`, and `Content-Bits` headers.
- Anthropic messages with model `ecnu-max[1m]` returned `401` with
  `{"detail":"Error code: 401 - {'detail': '获取第三方元数据失败'}"}`, while
  plain `ecnu-max` requests work. The documented suffix handling may be broken
  or depend on unlisted account metadata.

Everything else verified as documented on the same date: chat completions,
thinking with `reasoning_effort` (including `reasoning_content` omission in
non-tool multi-turn), tool calling, vision content parts, structured output,
Responses API including `reasoning.effort`, embeddings (scalar and array,
1024 dims), rerank, Anthropic model mapping and `output_config.effort`, image
generation, TTS default and new voices, and the `422` validation shape.

## Official Sources

- Authorization: https://developer.ecnu.edu.cn/vitepress/llm/authorization.html
- Models: https://developer.ecnu.edu.cn/vitepress/llm/model.html
- Thinking: https://developer.ecnu.edu.cn/vitepress/llm/thinking.html
- Chat Completions: https://developer.ecnu.edu.cn/vitepress/llm/api/completions.html
- Responses: https://developer.ecnu.edu.cn/vitepress/llm/api/responses.html
- Vision: https://developer.ecnu.edu.cn/vitepress/llm/api/vision.html
- Embeddings: https://developer.ecnu.edu.cn/vitepress/llm/api/embedding.html
- Rerank: https://developer.ecnu.edu.cn/vitepress/llm/api/rerank.html
- Image generation: https://developer.ecnu.edu.cn/vitepress/llm/api/imagegenerate.html
- Text-to-speech: https://developer.ecnu.edu.cn/vitepress/llm/api/audio.html
- Model list: https://developer.ecnu.edu.cn/vitepress/llm/api/models.html
- Anthropic compatibility: https://developer.ecnu.edu.cn/vitepress/llm/api/anthropic.html
- Structured output: https://developer.ecnu.edu.cn/vitepress/llm/api/structuredoutput.html
- Embed iFrame: https://developer.ecnu.edu.cn/vitepress/llm/api/embediframe.html
- Local deployment and data security: https://developer.ecnu.edu.cn/vitepress/llm/security.html
- Developer agreement (token rules): https://developer.ecnu.edu.cn/vitepress/llm/tos.html
