# Production engineering

Read this when an integration moves beyond a single test call: workers, batch
jobs, retries, cost control, or error handling. Numbers marked *documented*
come from the official pages linked in [models.md](models.md) and can change;
recheck them before hard-coding. Items marked *observed* come from
live checks listed in [troubleshooting](troubleshooting.md).

## Concurrency

*Documented:* each user may have at most 3 in-flight requests on `ecnu-max`
and 5 on `ecnu-plus`, counted per model; the next one gets `429` immediately.
The cap is per user, not per key or per process, so several keys of one
account and several workers share it.

- Gate each model with its own limiter sized at or below the cap. With several
  processes, use one shared limiter (or give each process a fixed share);
  a per-process semaphore alone oversubscribes.
- Other endpoints publish no cap. Run embedding, rerank, image, TTS and decision
  calls serially or with low parallelism and treat `429` as the limit signal.

## Retries follow side effects, not status codes

SDKs retry by default (`openai` and `anthropic` use `max_retries=2`, including
on timeouts). Set `max_retries=0` and decide per request:

| Failure | Action |
|---|---|
| `400` / `422` | Fix the request; `422` carries a `detail` list |
| `401` | Check the model name first: unsupported models return `401` (*observed*) |
| `429` | Wait for an in-flight request to finish, then retry with jittered backoff; if the 7-day quota is exhausted, stop |
| Plain-text `500` right after an unusual parameter | Likely invalid input (*observed* for unsupported effort and TTS voice); do not retry unchanged |
| Timeout, dropped connection or `5xx` on embedding, rerank or decision | A bounded retry is safe (no side effects); embedding and rerank are charged per attempt |
| Same on chat, image or TTS | Do not resubmit automatically: the request may have completed and been charged (image: 30 credits) |

The docs do not define a body that distinguishes concurrency `429` from quota
exhaustion; use your in-flight count and the usage dashboard.

`classify_failure` encodes this table for a direct-HTTP client. `endpoint` is
the path after the API base, such as `/chat/completions`:

```python
IDEMPOTENT_ENDPOINTS = {"/embeddings", "/rerank", "/systemone"}


def classify_failure(endpoint, status, body, transport_error=False):
    """Return (action, summary); action is retry, fix-request, check-account or stop."""
    text = body.decode("utf-8", "replace") if isinstance(body, bytes) else str(body or "")
    summary = f"HTTP {status}: {text[:200]}" if status else "no HTTP response"
    if transport_error or status is None or status >= 500:
        if status is not None and status < 600 and not text.lstrip().startswith(("{", "[")):
            summary += " (plain-text error; check the request values before retrying)"
        return ("retry" if endpoint in IDEMPOTENT_ENDPOINTS else "stop"), summary
    if status == 429:
        return "retry", summary + " (wait for an in-flight request or check the quota)"
    if status in (401, 403):
        return "check-account", summary + " (verify the model name before rotating keys)"
    return "fix-request", summary
```

Log `summary` after redaction; never retry in parallel.

## Timeouts and streaming

Set an explicit client timeout on every call. Thinking requests and long
outputs can take minutes; stream interactive chat so the user sees progress
and the connection is not idle. The decision gateway times out at about 180
seconds (*documented*), so give it at least 190.

## Cost

- *Documented:* `ecnu-max` and `ecnu-plus` token prices double on weekdays
  08:00–18:00 Beijing time; weekends and public holidays are off-peak.
  Fixed-price endpoints are unaffected. Schedule batch jobs off-peak.
- *Documented:* cached input costs one tenth of uncached input. Keep a stable
  prefix (system prompt, tool definitions, shared documents) and append the
  variable part; `usage.prompt_tokens_details.cached_tokens` shows hits.
- *Documented:* personal tokens share a rolling 7-day pool. Production systems
  serving ECNU students and staff can request a separate pool (see the
  [quota page](https://developer.ecnu.edu.cn/vitepress/llm/limit.html)).
- *Observed:* sending `reasoning_effort` alone enables thinking, which bills
  reasoning as output. Omit it when thinking should be off.

## Validate locally what the server accepts

The service accepts some out-of-contract input without an error (*observed*):
over-length embedding and rerank text, `temperature` above 1, and undocumented
effort tiers on `ecnu-max`. Others fail as plain `500`. Enforce the documented
limits before sending: text length per endpoint, sampling ranges, effort tiers
per model (`ecnu-max`: `low`/`high`/`max`; `ecnu-plus`: `low`/`medium`/`xhigh`),
and the documented voice list.

## Responses you should not over-trust

- Error bodies come in three shapes: `{"detail": "..."}` or a `detail` list,
  `{"error": {...}}`, and plain text. Parse without assuming JSON.
- The response `model` is a backend label (for example `qwen3.8-flash`); log
  the requested model and do not assert equality.
- Reasoning-token counts live in different `usage` fields (*observed*):
  `ecnu-max` uses `completion_tokens_details.reasoning_tokens`, `ecnu-plus` a
  top-level `reasoning_tokens`, Responses `output_tokens_details.reasoning_tokens`.
  A reply can report reasoning tokens without `reasoning_content`; read all
  three before concluding thinking was off.
- A model listed by `/models` is not a supported contract (*observed*).

## Secrets and data

Read the key from the environment or a secret manager. Never log
`Authorization`, image URLs, embed tickets or `reasoning_content`. Models run
on campus servers, but the [security page](https://developer.ecnu.edu.cn/vitepress/llm/security.html)
allows temporary cloud fallback; check it and the developer agreement before
sending personal or confidential data.
