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
upstream model background, application policy, and unverified claims separate.

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
  roots, request fields, limits, response shapes, and URL-parameter chat.
- Read [references/models.md](references/models.md) for model selection,
  aliases, thinking modes, credits, quotas, deployment notes, and upstream
  Qwen3.8 / DeepSeek / DSpark background with ECNU-specific boundaries.
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
| General text, tools, lower token price | `ecnu-plus` |
| Complex text or code | `ecnu-max` |
| Image understanding | `ecnu-plus` |
| Structured JSON | `ecnu-plus` or `ecnu-max` |
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

#### Structured output

- Both primary dialog models support `json_schema` and `json_object`.
- Parse raw JSON without removing Markdown fences; check completion and
  validate the supplied schema. Valid structure does not ensure correct facts.

### 6. Protect secrets, data, and credits

Before a real request:

- recheck the current official quota and pricing page, then calculate a
  conservative planned cost from those documented prices;
- use 50 credits as the default ceiling and do not run a larger plan without
  separate user authorization;
- use only `ECNU_API_KEY` from the environment; never accept a key through a
  command-line argument;
- remove secrets and unnecessary personal or confidential data;
- verify that existing conversation authorization covers the account, supplied
  content, ECNU destination, and planned purpose; ask only if that coverage is
  missing or materially changes, and preserve any explicit per-action approval;
- execute requests serially; and
- never retry a POST after an ambiguous timeout or connection failure.

Reuse authorization within the same approved batch. Track cumulative planned
and consumed credits against the batch ceiling; do not reset the allowance
for each request. Missing data authorization blocks only the affected request,
not independent offline preparation or validation.

If the full plan exceeds 50 credits, preserve the core dialog, embedding,
rerank, compatibility, and error checks; prefer one TTS PCM check; run at most
one documented image-generation case; and skip expanded voices and
undocumented model probes.

If a key has already been pasted into a chat or public location, recommend
revoking or rotating it after testing.

### 7. Execute and verify

Use the smallest profile that answers the question. Sanitized reports belong
under the ignored `.live-artifacts/` directory:

```bash
python3 scripts/smoke_test.py --profile auth --max-credits 0 --output .live-artifacts/auth.json
python3 scripts/smoke_test.py --profile core --max-credits 50 --output .live-artifacts/core.json
python3 scripts/smoke_test.py --profile compatibility --max-credits 50 --output .live-artifacts/compatibility.json
python3 scripts/smoke_test.py --profile billable --max-credits 50 --output .live-artifacts/billable.json
python3 scripts/smoke_test.py --profile all --max-credits 50 --output .live-artifacts/all.json
```

The default profile is `auth`. The runner reads `ECNU_API_KEY`, executes
serially with POST retries disabled, reserves estimated credits before each
request, skips cases that would exceed the ceiling, and emits response
structure rather than generated content. A credit estimate is not proof of the
service's actual debit.

### 8. Report provenance

Label important conclusions as one of:

- **`documented`** — supported by the current official ECNU documentation.
- **`upstream-background`** — supported by original model cards or papers;
  not proof of ECNU endpoint capabilities, defaults, or performance.
- **`observed`** — reproduced against the live service at a stated date.
- **`application-policy`** — a local safety, cost, or reliability constraint;
  not an ECNU platform guarantee.
- **`unverified`** — inferred, historical, or not reproducible in the current
  environment.

Do not silently promote an observed deviation into a documented guarantee.

### 9. Finish repository work

When repository files changed, finish with offline, format, and secret checks:

```bash
python3 scripts/validate_skill.py
python3 -m unittest discover -s tests -v
python3 -m compileall scripts tests
uvx --from skills-ref agentskills validate "$PWD"
git grep -nE 'sk-[A-Za-z0-9_-]{16,}'
git grep -nE 'Authorization:[[:space:]]*Bearer[[:space:]]+[^<"$]'
git diff --check
```

Review every secret-scan match; no tracked literal credential may remain.
Variable-based test fixtures may match the coarse Bearer expression. If `uvx`
is not available, report that validator as not run rather than treating it as
live API evidence.

## High-value gotchas

- `GET /models` is runtime discovery, not a reliable authentication test.
- A model appearing in `/models` does not prove that a capability is usable.
- Use `ecnu-max[1m]` only when an Anthropic tool requires the suffix to
  advertise long context. Consider plain `ecnu-max` only when the same
  credential already succeeds with that model, the suffixed request returns
  the observed suffix-specific `401` metadata error, and the caller accepts
  the shorter advertised context.
- TTS errors may not match the documented JSON shape; preserve the HTTP status,
  content type, and a bounded redacted body sample.
- Do not assume the documented PCM metadata headers are present; check them at
  runtime and configure the format explicitly when they are absent.
- `422` means request validation failed; inspect `detail`.
- `429` may represent quota exhaustion, rate control, or short-term service
  protection. Stop parallel retries and inspect credits first.

## Official documentation

- Models: https://developer.ecnu.edu.cn/vitepress/llm/model.html
- Thinking: https://developer.ecnu.edu.cn/vitepress/llm/thinking.html
- API index: https://developer.ecnu.edu.cn/vitepress/llm/api/models.html
- Responses: https://developer.ecnu.edu.cn/vitepress/llm/api/responses.html
- Structured output: https://developer.ecnu.edu.cn/vitepress/llm/api/structuredoutput.html
- URL chat: https://developer.ecnu.edu.cn/vitepress/llm/api/urlchat.html
- Quotas: https://developer.ecnu.edu.cn/vitepress/llm/limit.html
- Errors: https://developer.ecnu.edu.cn/vitepress/llm/error.html
- Release notes: https://developer.ecnu.edu.cn/vitepress/llm/release.html
- Data security: https://developer.ecnu.edu.cn/vitepress/llm/security.html
- Developer agreement: https://developer.ecnu.edu.cn/vitepress/llm/tos.html
- Service status: https://chat.ecnu.edu.cn/status
