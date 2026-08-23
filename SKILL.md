---
name: ecnu-api
description: >
  Implement, review, test, or troubleshoot integrations with the ECNU
  (East China Normal University) LLM Open Platform at chat.ecnu.edu.cn.
  Use for OpenAI-compatible Chat Completions and Responses APIs, multimodal
  input, embeddings, rerank, image generation, text-to-speech, structured
  output, model discovery, Anthropic-compatible clients, authentication,
  credits, quotas, and API errors. Do not use for general ECNU information
  or unrelated DeepSeek and Qwen questions.
---

# ECNU LLM Open Platform API

Use this skill to turn ECNU API documentation into a safe, verifiable
integration. The current official ECNU developer documentation is the
authority for documented contracts. Keep documented facts, live observations,
and application policy separate.

## Core rules

1. Select the protocol root before constructing a request.
2. Use only fields documented by ECNU or explicitly verified against the
   current service.
3. Do not assume that every OpenAI or Anthropic feature is implemented merely
   because an endpoint is compatible with that protocol.
4. Keep API keys in environment variables. Never put a real key in source,
   command history, examples, logs, screenshots, or committed test output.
5. Treat live observations as point-in-time evidence, not permanent contracts.
6. Avoid parallel calls. Run batches sequentially unless ECNU documents a safe
   concurrency policy.

## Workflow

### 1. Classify the request

Determine whether the user wants:

- an explanation;
- implementation or code review;
- troubleshooting;
- a live capability check;
- a cost or quota calculation.

Do not execute a real request when the user only asks for documentation or
sample code.

### 2. Load only the relevant reference

- Read [references/api_reference.md](references/api_reference.md) for endpoint
  roots, request fields, limits, and response shapes.
- Read [references/models.md](references/models.md) for model selection,
  aliases, thinking modes, credits, quotas, and deployment notes.
- Read [references/examples.md](references/examples.md) for minimal Python and
  HTTP examples.
- Read [references/workflows.md](references/workflows.md) for implementation,
  review, troubleshooting, retry, privacy, and live-verification procedures.
- Read [references/known_deviations.md](references/known_deviations.md) when
  diagnosing behavior that conflicts with the official documentation.

Do not load every reference for a narrow task.

### 3. Select the protocol root

| Protocol | Base or full URL |
|---|---|
| OpenAI-compatible | `https://chat.ecnu.edu.cn/open/api/v1` |
| Anthropic-compatible | `https://chat.ecnu.edu.cn/open/api/anthropic` |
| Embed iFrame | `https://chat.ecnu.edu.cn/open/api/embed/app` |

The Anthropic messages URL is:

```text
https://chat.ecnu.edu.cn/open/api/anthropic/v1/messages
```

Never append the Anthropic path to the OpenAI-compatible `/v1` base.

### 4. Select a model

| Task | Preferred model |
|---|---|
| General text, tools, lower latency | `ecnu-plus` |
| Complex text or code | `ecnu-max` |
| Image understanding | `ecnu-plus` |
| Embeddings | `ecnu-embedding-small` |
| Rerank | `ecnu-rerank` |
| Image generation | `ecnu-image` |
| Text-to-speech | `ecnu-tts` |

Use `ecnu-max` and `ecnu-plus` for new dialog integrations. Treat historical
names as compatibility aliases.

### 5. Validate the request contract

#### Embeddings

- `input` must be one string or an array of strings.
- Do not send OpenAI token-ID arrays.
- ECNU documents a 1024-float output vector.
- The direct ECNU request documents `model` and `input`; do not add an
  unsupported dimension-selection request field.
- With LangChain `OpenAIEmbeddings`, set
  `check_embedding_ctx_length=False` so raw strings are sent. Verify the
  returned vector length after the request.

#### Rerank

- `documents` must be a string array.
- `query` must be a string.
- Each document is limited to 8192 characters.
- `top_n` defaults to 5. ECNU publishes no maximum document count, maximum
  `top_n`, or query-length limit.

#### Vision

- Use Chat Completions with structured `text` and `image_url` content parts.
- Use `ecnu-plus`.
- A public URL or base64 data URL may be used.
- Do not convert a ChatECNU web-UI upload limit into an API limit.

#### Image and audio

- Image prompts are limited to 1024 characters; prompts over 500 characters
  may be compressed.
- Image URLs expire after 24 hours.
- TTS input is limited to 4096 characters.
- TTS speed is 0.25 through 4.0.

### 6. Protect secrets, data, and credits

Before a real request:

- use an environment variable such as `ECNU_API_KEY`;
- remove secrets and unnecessary personal or confidential data;
- confirm the user intended to send the supplied content to ECNU;
- state when image generation, TTS, or other calls may consume credits;
- never blindly retry a billable request after an ambiguous timeout.

If a key has already been pasted into a chat or public location, recommend
revoking or rotating it after testing.

### 7. Execute and verify

For reproducible checks, run:

```bash
python scripts/smoke_test.py
```

This default profile performs model-list checks only. Low-cost POST probes are
opt-in:

```bash
python scripts/smoke_test.py --low-cost --anthropic
```

The script reads `ECNU_API_KEY`, redacts key-shaped strings, and emits a
structural JSON report rather than model output.

### 8. Report provenance

Label important conclusions as one of:

- **Documented** — supported by the current official ECNU documentation.
- **Observed** — reproduced against the live service at a stated date.
- **Unverified** — inferred, historical, or not reproducible in the current
  environment.

Do not silently promote an observed deviation into a documented guarantee.

## High-value gotchas

- `GET /models` is runtime discovery, not a reliable authentication test.
- A model appearing in `/models` does not prove that a capability is usable.
- Use `ecnu-max[1m]` only when an Anthropic tool requires the suffix to
  advertise long context. Fall back to plain `ecnu-max` if the suffix returns
  an authentication or metadata error.
- TTS errors may not match the documented JSON shape; preserve the HTTP status,
  content type, and a bounded redacted body sample.
- Do not depend on optional PCM metadata headers without checking them at
  runtime.
- `422` means request validation failed; inspect `detail`.
- `429` may represent quota exhaustion, rate control, or short-term service
  protection. Stop parallel retries and inspect credits first.

## Official documentation

- Models: https://developer.ecnu.edu.cn/vitepress/llm/model.html
- Thinking: https://developer.ecnu.edu.cn/vitepress/llm/thinking.html
- API index: https://developer.ecnu.edu.cn/vitepress/llm/api/models.html
- Responses: https://developer.ecnu.edu.cn/vitepress/llm/api/responses.html
- Quotas: https://developer.ecnu.edu.cn/vitepress/llm/limit.html
- Errors: https://developer.ecnu.edu.cn/vitepress/llm/error.html
- Release notes: https://developer.ecnu.edu.cn/vitepress/llm/release.html
- Data security: https://developer.ecnu.edu.cn/vitepress/llm/security.html
- Developer agreement: https://developer.ecnu.edu.cn/vitepress/llm/tos.html
- Service status: https://chat.ecnu.edu.cn/status
