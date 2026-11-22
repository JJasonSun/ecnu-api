---
name: ecnu-api
description: >
  Connect an application, SDK or coding agent to the ECNU / ChatECNU LLM Open
  Platform at chat.ecnu.edu.cn, audit or migrate an existing integration,
  harden it for production, or diagnose an ECNU API failure. Covers chat, thinking, tools, vision, Responses, JSON output,
  text/image embeddings and rerank, ecnu-decision classification and scoring,
  image generation/editing, TTS, Anthropic-compatible clients, concurrency,
  retries and credit cost. Use whenever code or config contains
  chat.ecnu.edu.cn/open/api, ECNU_API_KEY or an ecnu-* model name. Not for general ECNU information or unrelated model questions.
---

# ECNU API integration

The official documentation is the contract; this skill does not copy it. It
adds what the docs leave out: which page and model fit a task, production
practice, small tested recipes, and where the live service currently differs
from the docs. Finish the user's integration rather than auditing the platform,
and keep their framework and model unless the task requires a change.

## Start with a working connection

For a new ordinary text integration, start with `ecnu-plus` (an application
default, not a quality ranking). Read the key from `ECNU_API_KEY`; a missing
key does not block writing code. This example makes one real request, so do
not run it for a code-only task:

```python
import os
from openai import OpenAI

client = OpenAI(
    api_key=os.environ["ECNU_API_KEY"],
    base_url="https://chat.ecnu.edu.cn/open/api/v1",
    timeout=60.0,
    max_retries=0,
)
response = client.chat.completions.create(
    model="ecnu-plus",
    messages=[{"role": "user", "content": "Reply with a short greeting."}],
    max_tokens=128,
)
if not response.choices or response.choices[0].finish_reason != "stop":
    raise RuntimeError("No complete text response; inspect the result before retrying")
text = response.choices[0].message.content
if not text:
    raise RuntimeError("The response contained no text")
print(text)
```

| Client | Base URL |
|---|---|
| OpenAI-compatible | `https://chat.ecnu.edu.cn/open/api/v1` |
| Anthropic-compatible | `https://chat.ecnu.edu.cn/open/api/anthropic` (messages at `/v1/messages` below it) |
| Embed ticket endpoint | `https://chat.ecnu.edu.cn/open/api/embed/app` |

Never append the Anthropic path to the OpenAI `/v1` base.

## Route the task

Open only the row you need. Official pages are under
`https://developer.ecnu.edu.cn/vitepress/llm/`.

| Task | Official contract | Local help |
|---|---|---|
| Chat, streaming, tools, image input | [Chat Completions](https://developer.ecnu.edu.cn/vitepress/llm/api/completions.html) | [Thinking and tool history](references/examples.md#thinking-and-tool-history) |
| Thinking switch and effort | [Thinking](https://developer.ecnu.edu.cn/vitepress/llm/thinking.html) | Same recipe; tiers differ per model |
| JSON Schema or JSON object output | [Structured output](https://developer.ecnu.edu.cn/vitepress/llm/api/structuredoutput.html) | Check completion, parse raw JSON, validate the schema |
| Responses-compatible client | [Responses](https://developer.ecnu.edu.cn/vitepress/llm/api/responses.html) | Check each advanced tool or event you rely on |
| Anthropic SDK or client | [Anthropic API](https://developer.ecnu.edu.cn/vitepress/llm/api/anthropic.html) | [Anthropic recipe](references/examples.md#anthropic-sdk) |
| Coding agent or desktop client (Claude Code, Codex, Cline, WorkBuddy, …) | [Agent tool guides](https://developer.ecnu.edu.cn/vitepress/llm/agent/claude-code.html) and [more tools](https://developer.ecnu.edu.cn/vitepress/llm/case/userkey.html) | Follow the official guide for that tool |
| Text or multimodal embeddings | [Embeddings](https://developer.ecnu.edu.cn/vitepress/llm/api/embedding.html) | [LangChain](references/examples.md#langchain-embeddings), [multimodal](references/examples.md#multimodal-retrieval) |
| Rerank | [Rerank](https://developer.ecnu.edu.cn/vitepress/llm/api/rerank.html) | [Multimodal retrieval](references/examples.md#multimodal-retrieval) |
| Classification, yes/no judgment, scoring | [Decision](https://developer.ecnu.edu.cn/vitepress/llm/api/decision.html) | [Decision recipe](references/examples.md#structured-decision): `/systemone`, not chat |
| Generate or edit images | [Generation](https://developer.ecnu.edu.cn/vitepress/llm/api/imagegenerate.html), [editing](https://developer.ecnu.edu.cn/vitepress/llm/api/imageedit.html) | [Image recipe](references/examples.md#image-generation-and-editing) |
| Text-to-speech | [Audio](https://developer.ecnu.edu.cn/vitepress/llm/api/audio.html) | [Troubleshooting](references/troubleshooting.md): non-JSON errors, missing PCM headers |
| Embed an iframe or link a prefilled question | [Embed](https://developer.ecnu.edu.cn/vitepress/llm/api/embediframe.html), [URL chat](https://developer.ecnu.edu.cn/vitepress/llm/api/urlchat.html) | Tickets are credentials; opening a submit link sends data |
| Model choice, prices, quotas, data handling | [Models](https://developer.ecnu.edu.cn/vitepress/llm/model.html), [quota](https://developer.ecnu.edu.cn/vitepress/llm/limit.html) | [Model snapshot and account pages](references/models.md) |
| Workers, batch jobs, retries, cost control | — | [Engineering](references/engineering.md) |
| Check, migrate or productionize an existing ECNU integration | [Release notes](https://developer.ecnu.edu.cn/vitepress/llm/release.html) | [Audit checklist](references/audit.md): read-only report first |
| An error or unexpected behavior | [Error codes](https://developer.ecnu.edu.cn/vitepress/llm/error.html) | [Troubleshooting](references/troubleshooting.md) |

Protocol compatibility does not mean every OpenAI or Anthropic field works.
If an official page is unreachable, continue offline with the local material
and say which value could not be rechecked.

## Before shipping

These behaviors break code that worked in a single test; details and evidence
are in [engineering](references/engineering.md):

- Concurrency is capped per user and model (`ecnu-max` 3, `ecnu-plus` 5);
  extra requests get an immediate `429`. Limit in-flight requests per model.
- SDKs retry by default; set `max_retries=0` and retry only side-effect-free
  calls, because a resubmitted chat, image or TTS request can be charged twice.
- Effort tiers differ per model, and an unsupported one returns a plain `500`.
  Sending `reasoning_effort` alone turns thinking on.
- The service silently accepts some over-limit input; validate it locally.
- Token prices double during weekday daytime peak hours; run batches off-peak.

## Execution boundary

Make live requests only when needed and covered by the user's authorization
for the account, data, destination, purpose and budget; reuse that scope rather
than asking again. Never ask for a key in chat or log credentials, private
prompts or reasoning. Missing permission blocks the request, not offline work.

For a live check, use synthetic input, run serially, and pick the smallest
[runner case](references/troubleshooting.md#run-a-live-check). Its 50-credit
default is a ceiling, not permission to spend. Never automatically repeat a
possibly accepted POST after a timeout or dropped connection.

Finish with the requested code or answer and state what was actually checked.
