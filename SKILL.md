---
name: ecnu-api
description: >
  ECNU (East China Normal University) LLM Open Platform API integration.
  Provides OpenAI-compatible chat completions, embeddings, rerank, image
  generation, TTS, vision, structured output, and Anthropic-compatible API
  access. Use when Codex needs to call ECNU or ChatECNU LLM APIs, write code for
  chat.ecnu.edu.cn endpoints, configure Claude Code or Anthropic SDK against
  ECNU, or answer questions about ECNU API authentication, models, quotas,
  errors, prompts, or terms. Triggers: "ecnu api", "ECNU 大模型",
  "华东师范大学 API", "ChatECNU", "chat.ecnu.edu.cn", "ecnu-plus",
  "ecnu-max", "ecnu-embedding-small", "ecnu-rerank", "ecnu-image",
  "ecnu-tts".
---

# ECNU LLM Open Platform API

Base URL: `https://chat.ecnu.edu.cn/open/api/v1`

## Authentication

Use OpenAI-compatible bearer token authentication.

```http
Authorization: Bearer <your_api_key>
Content-Type: application/json
```

Obtain an API key by logging in to [ChatECNU](https://chat.ecnu.edu.cn), clicking
the avatar, and selecting "我的令牌" (My Token).

## API Overview

| Category | Endpoint | Model |
|---|---|---|
| Chat Completions | `POST /chat/completions` | `ecnu-max`, `ecnu-plus` |
| Vision (Multimodal) | `POST /chat/completions` | `ecnu-plus` / `ecnu-vl` compatibility alias |
| Embeddings | `POST /embeddings` | `ecnu-embedding-small` |
| Rerank | `POST /rerank` | `ecnu-rerank` |
| Image Generation | `POST /images/generations` | `ecnu-image` |
| Text-to-Speech | `POST /audio/speech` | `ecnu-tts` |
| Model List | `GET /models` | N/A |
| Anthropic Compatible | `POST /anthropic/v1/messages` | `ecnu-plus`, `ecnu-max` |
| Structured Output | `POST /chat/completions` | `ecnu-plus`, `ecnu-turbo` |
| Embed iFrame (Experimental) | `POST /open/api/embed/app` | N/A |

Use any OpenAI-compatible SDK with:

```python
base_url = "https://chat.ecnu.edu.cn/open/api/v1"
```

## Core Models

| Model | Base Model | Context | Thinking | Tools | Vision |
|---|---|---|---|---|---|
| `ecnu-max` | DeepSeek-V4-Flash | 1M | Supported, default off | Yes | No |
| `ecnu-plus` | Qwen3.6-27B | 256K | Supported, default off | Yes | Yes |

Compatibility aliases are retained for older integrations. Prefer `ecnu-max` or
`ecnu-plus` for new chat integrations. Use `ecnu-plus` for image understanding;
`ecnu-max` no longer supports vision.

## Reference Files

Read these files based on the task:

- For endpoint parameters, request shapes, response fields, and API-specific
  caveats: [references/api_reference.md](references/api_reference.md)
- For model details, aliases, quotas, credits, and error codes:
  [references/models.md](references/models.md)
- For Python SDK and direct HTTP examples:
  [references/examples.md](references/examples.md)

## Key Guidelines

- All listed models are locally deployed on campus servers by default. ECNU
  notes that cloud fallback may be used temporarily in special cases such as
  upgrades, failures, or overload.
- Avoid parallel API calls; wait for each response before sending the next
  request for better stability.
- Credits are consumed for all API calls. The unified credits quota algorithm
  took effect on 2026-06-01.
- Enable thinking mode with `{"thinking": {"type": "enabled"}}`.
- Native web search capability was removed on 2025-03-20; use tool calling or
  another external search path instead.
- Image URLs returned by image generation are valid for 24 hours only.
- TTS input is limited to 4096 characters. Image generation prompts are limited
  to 1024 characters and may be compressed when over 500 characters.
- For LangChain embeddings, set `check_embedding_ctx_length=False` so LangChain
  does not tokenize the input into OpenAI token IDs before calling ECNU.

## Official Documentation

When precision matters, verify against the official ECNU developer docs:

- Models: https://developer.ecnu.edu.cn/vitepress/llm/model.html
- Authorization: https://developer.ecnu.edu.cn/vitepress/llm/authorization.html
- Quotas: https://developer.ecnu.edu.cn/vitepress/llm/limit.html
- Errors: https://developer.ecnu.edu.cn/vitepress/llm/error.html
- API reference: https://developer.ecnu.edu.cn/vitepress/llm/api/models.html
