# ECNU API Reference

## Table of Contents

- [Base URL and Authentication](#base-url-and-authentication)
- [Chat Completions](#chat-completions)
- [Vision Multimodal Chat](#vision-multimodal-chat)
- [Embeddings](#embeddings)
- [Rerank](#rerank)
- [Image Generation](#image-generation)
- [Text-to-Speech](#text-to-speech)
- [Model List](#model-list)
- [Anthropic Compatible API](#anthropic-compatible-api)
- [Structured Output](#structured-output)
- [Embed iFrame Experimental](#embed-iframe-experimental)
- [Official Sources](#official-sources)

---

## Base URL and Authentication

OpenAI-compatible API base URL:

```text
https://chat.ecnu.edu.cn/open/api/v1
```

Headers:

```http
Authorization: Bearer <your_api_key>
Content-Type: application/json
```

## Chat Completions

OpenAI-compatible chat completion endpoint.

```http
POST /chat/completions
```

### Request Parameters

| Parameter | Type | Required | Description |
|---|---|---|---|
| `model` | string | Yes | Prefer `ecnu-max` or `ecnu-plus` |
| `messages` | array | Yes | Message objects with `role` and `content` |
| `stream` | boolean | No | Enable SSE streaming |
| `temperature` | float | No | Sampling temperature, 0-1 |
| `top_p` | float | No | Nucleus sampling, 0-1 |
| `thinking` | object | No | `{"type": "enabled"}` or `{"type": "disabled"}` |
| `tools` | array | No | OpenAI-compatible function tool definitions |
| `max_tokens` | integer | No | Maximum tokens to generate |
| `response_format` | object | No | Used for structured output |

`search_mode` is deprecated because native web search was removed on
2025-03-20. Use tool calling or another search path instead.

### Response Fields

| Field | Type | Description |
|---|---|---|
| `id` | string | Chat completion ID |
| `object` | string | `chat.completion` |
| `created` | integer | Creation timestamp |
| `choices[].message.content` | string | Response text |
| `choices[].message.reasoning_content` | string | Reasoning content when thinking is enabled |
| `choices[].message.tool_calls` | array | Tool calls when the model requested function execution |
| `choices[].finish_reason` | string | Stop reason |
| `usage.*_tokens` | integer | Estimated token usage |

### Streaming Response

When `stream: true`, chunks are sent as SSE `data:` lines and end with
`data: [DONE]`.

## Vision Multimodal Chat

Vision uses the same `/chat/completions` endpoint. Use `ecnu-plus` for new
integrations. Some older examples use `ecnu-vl`, which is a compatibility alias
for `ecnu-plus`.

`ecnu-max` does not support image understanding.

### Message Content

Use structured content:

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

Supported image inputs:

- Base64 data URLs such as `data:image/jpeg;base64,<data>`
- Public image URLs

## Embeddings

OpenAI-compatible text embedding endpoint.

```http
POST /embeddings
```

| Parameter | Type | Required | Description |
|---|---|---|---|
| `model` | string | Yes | `ecnu-embedding-small` |
| `input` | string or array | Yes | Text input; each item max 8192 characters |

Response uses OpenAI-style `data[].embedding` vectors with 1024 dimensions.

For LangChain, set `check_embedding_ctx_length=False` when using
`OpenAIEmbeddings`; otherwise LangChain may tokenize input using OpenAI token IDs
before sending it to ECNU.

## Rerank

Cohere-compatible reranking endpoint.

```http
POST /rerank
```

| Parameter | Type | Required | Description |
|---|---|---|---|
| `model` | string | Yes | `ecnu-rerank` |
| `documents` | array | Yes | Document list; each document max 8192 characters |
| `query` | string | Yes | Query text |
| `return_documents` | boolean | No | Whether to return document text |
| `top_n` | integer | No | Number of results; default 5 |

Response fields include `id`, `results[].index`, `results[].relevance_score`,
and optionally `results[].document`.

## Image Generation

OpenAI-compatible image generation endpoint.

```http
POST /images/generations
```

| Parameter | Type | Required | Description |
|---|---|---|---|
| `model` | string | Yes | `ecnu-image` |
| `prompt` | string | Yes | Max 1024 characters; prompts over 500 chars may be compressed |
| `size` | string | No | `512x512`, `768x768`, `720x1280`, `1280x720`, `1024x1024`; default `512x512` |
| `response_format` | string | No | `url` or `b64_json`; default `url` |

URL responses are valid for 24 hours only. Error responses may include
`err_message` and a revised or masked prompt.

## Text-to-Speech

OpenAI-compatible text-to-speech endpoint.

```http
POST /audio/speech
```

| Parameter | Type | Required | Description |
|---|---|---|---|
| `model` | string | Yes | `ecnu-tts` |
| `input` | string | Yes | Text to convert; max 4096 characters |
| `voice` | string | No | `xiayu` or `liwa`; default `xiayu` |
| `response_format` | string | No | `mp3`, `opus`, `aac`, `flac`, `wav`, `pcm`; default `mp3` |
| `speed` | number | No | 0.25-4.0; default 1.0 |

The response body is binary audio data.

## Model List

OpenAI-compatible model listing endpoint.

```http
GET /models
```

No request body. Response uses OpenAI-style `object: "list"` and `data[]` model
objects with `id`, `object`, `created`, and `owned_by`.

## Anthropic Compatible API

ECNU provides an Anthropic-compatible endpoint for tools such as Claude Code.

Anthropic base URL:

```text
https://chat.ecnu.edu.cn/open/api/anthropic
```

Full messages endpoint:

```text
https://chat.ecnu.edu.cn/open/api/anthropic/v1/messages
```

Recommended environment variables:

```bash
export ANTHROPIC_BASE_URL=https://chat.ecnu.edu.cn/open/api/anthropic
export ANTHROPIC_AUTH_TOKEN=<your_api_key>
```

Model mapping:

| Anthropic-style model | ECNU model |
|---|---|
| `opus` series | `ecnu-max` |
| `sonnet` / `haiku` | `ecnu-plus` |
| `ecnu-plus` | `ecnu-plus` |
| `ecnu-max` | `ecnu-max` |

## Structured Output

Structured output uses XGrammar constrained decoding and is supported by
`ecnu-plus` and `ecnu-turbo`.

Use `response_format` with a JSON Schema:

```json
{
  "response_format": {
    "type": "json_schema",
    "json_schema": {
      "name": "info_extraction",
      "schema": {
        "type": "object",
        "properties": {
          "name": {"type": "string"},
          "department": {"type": "string"},
          "title": {"type": "string"}
        },
        "required": ["name", "department", "title"]
      }
    }
  }
}
```

Still provide clear prompts and sufficient `max_tokens`; structural correctness
does not guarantee semantic correctness.

## Embed iFrame Experimental

The embed iFrame API is experimental and may change. It returns a one-time URL
for embedding ChatECNU conversation UI into another system.

Endpoint path:

```http
POST /open/api/embed/app
```

Content types:

- `application/json`
- `application/x-www-form-urlencoded`

Required parameters:

| Parameter | Type | Description |
|---|---|---|
| `client_id` | string | Developer account ID |
| `client_secret` | string | Developer account secret |
| `userid` | string | User ID; ECNU docs recommend exam/student identifier where applicable |
| `username` | string | User name |
| `appid` | string | Assigned embed application ID |

Response fields:

| Field | Type | Description |
|---|---|---|
| `code` | integer | `0` indicates success |
| `message` | string | Status message |
| `data.ticket` | string | One-time ticket |
| `data.url` | string | iFrame URL |
| `data.expire` | integer | Lifetime in seconds |

Refresh the URL before the ticket expires. Reusing a one-time ticket invalidates
the access URL.

## Official Sources

- Models: https://developer.ecnu.edu.cn/vitepress/llm/model.html
- Authorization: https://developer.ecnu.edu.cn/vitepress/llm/authorization.html
- Chat completions: https://developer.ecnu.edu.cn/vitepress/llm/api/completions.html
- Vision: https://developer.ecnu.edu.cn/vitepress/llm/api/vision.html
- Embeddings: https://developer.ecnu.edu.cn/vitepress/llm/api/embedding.html
- Rerank: https://developer.ecnu.edu.cn/vitepress/llm/api/rerank.html
- Image generation: https://developer.ecnu.edu.cn/vitepress/llm/api/imagegenerate.html
- Text-to-speech: https://developer.ecnu.edu.cn/vitepress/llm/api/audio.html
- Anthropic compatible API: https://developer.ecnu.edu.cn/vitepress/llm/api/anthropic.html
- Structured output: https://developer.ecnu.edu.cn/vitepress/llm/api/structuredoutput.html
- Embed iFrame: https://developer.ecnu.edu.cn/vitepress/llm/api/embediframe.html
