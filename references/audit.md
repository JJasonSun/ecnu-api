# Audit an existing integration

Use this when a project already calls ECNU and the user wants it checked,
migrated after an ECNU release, or made production-ready. The audit is
read-only: report first, and change code only when the user asks. Each check
points to the evidence for it, so a finding is never just a style preference.

## 1. Find the call sites

Search the project, excluding dependencies and build output:

```bash
rg -n "chat\.ecnu\.edu\.cn|ECNU_API_KEY|ecnu-[a-z]" --glob '!{node_modules,.venv,venv,dist,build}/**'
```

Also follow configuration files and environment variables that feed a base
URL or model name. List each call site with its endpoint, model, client
library and whether it runs in a loop, worker or request handler.

## 2. Run the checks

Severity is the consequence, not the effort to fix:
**breaks** fails today; **load** fails or double-charges under concurrency or
network trouble; **silent** returns wrong or costly results without an error;
**cleanup** works but is outdated.

| Severity | Check | Look for | Fix | Evidence |
|---|---|---|---|---|
| breaks | Anthropic path on the OpenAI base | `/open/api/v1/anthropic`, `/v1/v1/messages` | Use the Anthropic base `https://chat.ecnu.edu.cn/open/api/anthropic` | [SKILL](../SKILL.md#start-with-a-working-connection) |
| breaks | Effort tier invalid for the model | `reasoning_effort`, `output_config`, `reasoning.effort` values; one setting shared by both models | The chosen model's tiers in the [snapshot](models.md#current-model-snapshot); a separate setting per model | [troubleshooting](troubleshooting.md#start-from-the-symptom) |
| breaks | `[1m]` model suffix | `ecnu-max[1m]`, client options that append it | Plain `ecnu-max` | [troubleshooting](troubleshooting.md#start-from-the-symptom) |
| breaks | Decision request shape | `"type": "bool"`, top-level `instructions`, `/chat/completions` with `ecnu-decision` | `noul`, per-question `instructions`, `POST /systemone` | [decision recipe](examples.md#structured-decision) |
| breaks | Undocumented model | Model IDs absent from the [snapshot](models.md#current-model-snapshot), such as `ecnu-music` | A documented model | [troubleshooting](troubleshooting.md#start-from-the-symptom) |
| load | SDK default retries | `OpenAI(`, `AsyncOpenAI(`, `Anthropic(`, `ChatOpenAI(` without `max_retries=0` | Disable, then retry per the table | [retries](engineering.md#retries-follow-side-effects-not-status-codes) |
| load | Retry wrappers around chat, image or TTS | `tenacity`, `backoff`, `@retry`, hand-written loops around those calls | Retry only embedding, rerank, decision and `429` | [retries](engineering.md#retries-follow-side-effects-not-status-codes) |
| load | Unbounded parallel calls | `asyncio.gather`, `ThreadPoolExecutor`, `Promise.all`, worker pools calling chat | One limiter per model at or below its cap, shared across processes | [concurrency](engineering.md#concurrency) |
| load | Personal token behind a shared service | One personal key serving a course, department or production system | Request a separate production quota pool (see the [quota page](https://developer.ecnu.edu.cn/vitepress/llm/limit.html)) | [cost](engineering.md#cost) |
| load | Missing or short timeouts | Clients without `timeout`; decision calls under 190 s | Explicit timeouts; stream long chat | [timeouts](engineering.md#timeouts-and-streaming) |
| load | Error parsing assumes JSON | `.json()` on error responses, `error["message"]` without checks | Parse `detail`, `error` and plain text | [errors](engineering.md#responses-you-should-not-over-trust) |
| silent | Effort sent with thinking off | `reasoning_effort` without `thinking`, or alongside `thinking: disabled` | Omit effort when thinking is off | [troubleshooting](troubleshooting.md#start-from-the-symptom) |
| silent | Limits not enforced locally | Embedding or rerank text without a length check; `temperature` above 1 | Validate before sending | [engineering](engineering.md#validate-locally-what-the-server-accepts) |
| silent | Mixed embedding spaces | Index and query built with different embedding models or dimensions | Re-embed with one model and dimension | [models](models.md#current-model-snapshot) |
| silent | Thinking history or usage misread | Assistant messages rebuilt by hand; reasoning tokens read from one `usage` field | Keep the returned message; read all counters | [recipe](examples.md#thinking-and-tool-history) |
| silent | Image URLs stored as assets | Saving `url` results without downloading | Download within 24 h or request `b64_json` | [image recipe](examples.md#image-generation-and-editing) |
| silent | Response model asserted | `response.model ==` the requested name | Log it; do not assert | [models](models.md#ecnu-specific-boundaries) |
| silent | Peak-hour batch jobs | Scheduled chat batches on weekday daytime | Run off-peak; keep a stable prompt prefix for caching | [cost](engineering.md#cost) |
| cleanup | Historical aliases | `ecnu-reasoner`, `ecnu-reasoner-lite`, `ecnu-turbo`, `ecnu-vl`, `InnoSpark`, `educhat-`, `ChatECNU`, `gpt-4` | Primary model plus explicit `thinking` | [models](models.md#current-model-snapshot) |
| security | Credentials in code or logs | `sk-` literals, logged headers or full requests, keys on the command line | Environment or secret manager; redact logs | [engineering](engineering.md#secrets-and-data) |

Recheck the model snapshot and effort tiers against the official pages before
reporting; an ECNU release can change them.

## 3. Report

```markdown
## ECNU integration audit
Scope: <files and call sites read>

| Severity | Location | Finding | Fix |
|---|---|---|---|

Questions only you can answer: <for example, is this job allowed to run at peak?>
Not checked: <files skipped, dynamic model names, behavior that needs a live call>
```

Order findings by severity and cite `file:line`. Mark a finding as uncertain
when a value comes from configuration you could not read.

## 4. Fix and verify (only when asked)

Change the smallest amount of code, explain each change and its reason, and
keep the user's framework. Run the project's own tests. A live check is
optional: name the [runner case](troubleshooting.md#run-a-live-check), state
its estimated cost, and get approval before sending it. Finish with what still
needs manual verification, such as load tests or prompt tuning after a model
change.
