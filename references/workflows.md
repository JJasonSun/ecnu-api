# Agent Workflows

Use these procedures when implementing, reviewing, troubleshooting, or live
testing ECNU API integrations.

## Implementation workflow

1. Identify the requested capability and protocol.
2. Read the relevant endpoint contract.
3. Select a primary model rather than a historical alias.
4. Build the smallest valid request.
5. Keep the API key in an environment variable.
6. Add explicit timeouts.
7. Validate the HTTP status, content type, and response shape.
8. Add advanced fields one at a time.
9. Keep calls sequential unless ECNU documents otherwise.
10. Report which behavior is documented and which is application policy.

Do not start from a generic OpenAI example and assume every field is supported.

## Code-review checklist

Check:

- correct base URL and endpoint;
- correct model for the capability;
- environment-based credential loading;
- no key, ticket, or embedded URL in logs;
- documented JSON types;
- no OpenAI token-ID input for ECNU embeddings;
- no undocumented embedding dimension request;
- either primary model for Chat Completions image understanding;
- explicit timeout;
- SDK retries disabled with `max_retries=0` for live probes;
- bounded error-body capture;
- no automatic parallel batch;
- no blind retry for billable POST requests;
- output validation;
- privacy and data-minimization requirements.

## Troubleshooting workflow

### 1. Capture evidence

Collect:

- UTC timestamp;
- endpoint and method;
- model name;
- HTTP status;
- response content type;
- bounded, redacted body sample;
- request field names and JSON types;
- SDK and version, if applicable;
- whether the request was direct HTTP or an SDK call.

Do not collect the API key or full sensitive prompt.

### 2. Classify the failure

| Symptom | First checks |
|---|---|
| `401` | credential source, expiry, protocol-specific auth handling |
| `403` | application or IP allowlist |
| `422` | missing field, wrong JSON type, unsupported request shape |
| `429` | credits, concurrent requests, burst protection |
| `5xx` JSON | proxy or backend error details |
| `5xx` plain text/HTML | preserve content type and bounded body |
| `200` with empty data | do not assume success; validate semantics |
| timeout or connection drop | mark inconclusive; the server may still have accepted the request |

For quota-related `429` responses, check the shared rolling 7-day allowance in
[models.md](models.md). There is no manual quota reset. Reduce usage, wait for
older consumption to leave the window, or contact the platform for quota needs.

### 3. Retry safely

Safe GET requests may use limited exponential backoff with jitter. The live
validator never retries POST requests.

Treat a POST timeout, connection drop, or truncated response as inconclusive.
Stop the flow and do not resubmit automatically; a later rerun is a new,
explicitly authorized request because the first request may have succeeded.

For image generation, TTS, or any billed operation, do not automatically
resubmit after a timeout or connection drop unless the service provides an
idempotency mechanism or the user explicitly accepts duplicate charges.

Never retry:

- unchanged invalid credentials;
- a deterministic `422`;
- a rejected request shape;
- a known unsupported model.

### 4. Compare sources

Use this order:

1. endpoint documentation;
2. model and quota pages;
3. dated known deviations;
4. a controlled live probe.

Do not use a single `/models` result as proof of endpoint support.

## Live-verification workflow

Use `scripts/smoke_test.py`. Its default `auth` profile performs only service
status and model-list GET requests. The script uses fixed ECNU hosts, serial
requests, explicit timeouts, no POST retry, and a credit ceiling.

Before opt-in POST probes:

1. verify that existing account-owner authorization covers this test batch,
   its data, ECNU destination, and purpose; ask only for missing or materially
   changed coverage, preserving any explicit per-action approval;
2. verify the approved credit ceiling and cumulative expected batch use;
   retain the default 50-credit ceiling and require separate authorization
   before exceeding it, without resetting the allowance per request;
3. minimize prompts and output tokens;
4. remove personal or confidential data;
5. set an explicit timeout;
6. avoid parallel execution;
7. write only a sanitized structural report.

The same approved batch does not require repeated confirmation. A pending
authorization blocks the affected live request; continue independent offline
preparation and checks within the existing scope.

Create reports only under the ignored artifact directory. Model discovery and
the documented `401` expectations are non-billable:

```bash
mkdir -p .live-artifacts
export ECNU_API_KEY="your-api-key"
python3 scripts/smoke_test.py --profile auth --max-credits 0 --timeout 30 \
  --account-type personal-token \
  --output .live-artifacts/auth.json
```

Exercise a valid-token gate, one invalid-token POST, and two request-shape
checks with a conservative allowance. These are real POST requests and require
account-owner authorization:

```bash
python3 scripts/smoke_test.py --profile core --max-credits 0.06 --timeout 60 \
  --case models_valid \
  --case error_invalid_token_post \
  --case error_missing_model \
  --case error_wrong_messages_type \
  --account-type personal-token \
  --output .live-artifacts/auth-and-422.json
```

The report stores the actual status and JSON shape even when the observed
service behavior differs from the documented `401` or `422` expectation. Do
not include `--strict` when the purpose is to collect deviation evidence.

A valid report records:

- test date and Python version;
- enabled profiles;
- status and content type per request;
- model IDs for `/models`;
- vector count and output length for embeddings;
- response structure, not successful model text or reasoning;
- bounded, redacted errors and allowlisted request IDs;
- transport errors as `inconclusive`, without credentials.

Interpret evidence per case:

| `result` | Meaning |
|---|---|
| `pass` | structural expectation passed in this dated run |
| `mismatch` | observed evidence differs from the documented expectation |
| `inconclusive` | no supportable endpoint conclusion, including transport failure |
| `skipped` | the case did not run and provides no live evidence |

`classification: observed` is point-in-time evidence, not a platform
guarantee. Reproduce a mismatch before changing `known_deviations.md`; never
promote an inconclusive or skipped case into a claim.

If the environment cannot reach the ECNU host, label the behavior unverified.
Do not update the known-deviation date.

## Model-discovery workflow

1. Read the model page for supported primary models and capabilities.
2. Call `/models` for runtime visibility.
3. Reject an empty list as inconclusive rather than authenticated success.
4. Ignore undocumented model IDs for production selection until a controlled
   capability probe succeeds.
5. Record capability probes by endpoint, because one model ID may not work
   across every endpoint.
6. Prefer documented primary names even when aliases are visible.

The `auth` command above is the executable discovery flow. A `200` response
with an empty `data` array does not prove authentication.

## Thinking-and-tool workflow

A tool step spans two requests. Append the returned assistant message, including
its `reasoning_content`, before the matching tool result. Preserve that exchange
in subsequent history, including later user turns. Keep reasoning in process
memory only; never print it or write it to a report. Clear it when the whole
conversation ends. The isolated probe below ends after its second request;
an ongoing Agent conversation does not. See [Agent development](agent_development.md).

```bash
python3 scripts/smoke_test.py --profile core --max-credits 1.2 --timeout 60 \
  --case models_valid \
  --case chat_thinking_tool_first \
  --case chat_thinking_tool_continue \
  --account-type personal-token \
  --output .live-artifacts/thinking-tool.json
```

The validator retains the first assistant message only in ephemeral run state,
submits one tool result, then clears that state before writing the sanitized
structural report.

This probe checks the documented `reasoning_content` field strictly. If it
differs from the current response, consult the
[live field observation](known_deviations.md#max-thinking-response-fields)
and validate continuation with the complete actual message; a mismatch alone
does not mean that thinking or tool use is unavailable.

## Structured-output workflow

After authorization for these low-cost POST probes, check both primary models
with both documented formats. These cases deliberately request Markdown
fences in the prompt to test the documented constrained-decoding behavior:

```bash
python3 scripts/smoke_test.py --profile core --max-credits 0.7 --timeout 60 \
  --case models_valid \
  --case structured_output_ecnu_plus \
  --case structured_output_ecnu_max \
  --case structured_output_json_object_ecnu_plus \
  --case structured_output_json_object_ecnu_max \
  --account-type personal-token \
  --output .live-artifacts/structured-output.json
```

Require a normally completed response and directly parse its raw content as
JSON. The schema cases check the fixture's required string fields and reject
extra fields; the JSON-object cases check only object structure. Do not repair
fences or judge factual extraction accuracy as part of the format contract.
The announced v3.3.0 fix alone is not proof of a live pass; keep old observation
dates unchanged until the affected behavior has been retested.

## Embedding workflow

1. Validate `input` as `str` or non-empty `list[str]`.
2. Reject integer arrays.
3. Keep batches conservative and sequential.
4. With LangChain, disable client-side OpenAI token conversion.
5. Do not send an undocumented dimension-selection field.
6. Sort returned items by `index`.
7. Assert that each returned vector has 1024 values.
8. Split or reduce a batch only after a meaningful validation or size error;
   do not claim the resulting size is an ECNU maximum.

## Anthropic workflow

1. Use the Anthropic root, not the OpenAI root.
2. Read `ECNU_API_KEY` from the environment and pass it to the SDK; set an
   explicit timeout and `max_retries=0`.
3. Prefer `ecnu-plus` or plain `ecnu-max`.
4. Use `ecnu-max[1m]` only when a tool requires the suffix to advertise long
   context.
5. After plain `ecnu-max` was verified with the same credential, fall back once
   on the known suffix-specific `401` and report the capability difference.
6. Do not generalize the suffix to OpenAI-compatible APIs.

Probe the suffix and its plain-model control narrowly:

```bash
python3 scripts/smoke_test.py --profile compatibility --max-credits 0.16 \
  --timeout 60 \
  --case models_valid \
  --case anthropic_max_1m \
  --case anthropic_max_1m_fallback_plain_max \
  --account-type personal-token \
  --output .live-artifacts/anthropic-1m.json
```

In application code, fall back once only when the `[1m]` request itself returns
the known suffix-specific `401`, plain `ecnu-max` was already verified with the
same credential, and the caller accepts losing the long-context capability
signal. Otherwise surface the error.

## Budgeted billable workflow

Select exact billable cases and set a ceiling equal to their conservative
planned cost. The script reserves budget before each request and stops before
the next case would exceed it. For example, after explicit authorization for a
5-credit TTS probe and a 30-credit image probe:

```bash
python3 scripts/smoke_test.py --profile billable --max-credits 35 --timeout 60 \
  --case models_valid \
  --case tts_xiayu_pcm \
  --case image_generation_documented \
  --account-type personal-token \
  --output .live-artifacts/billable.json
```

The image case attempts a bounded, public-network-safe validation without
persisting its one-time URL or generated bytes. A rejected download target or
transport failure is `inconclusive`; the billable POST is not retried.

## Security and privacy workflow

- Do not request a key in chat when an environment variable or secret manager
  can be used.
- If a key was exposed, recommend rotation.
- Do not send private documents, images, secrets, personal information, or
  internal prompts without a clear user request and appropriate handling basis.
- Do not log embed tickets, one-time URLs, authorization headers, or raw
  production prompts.
- Sanitize exception bodies because proxies may echo request details.
- Keep live-test artifacts out of version control.

## Result format

A useful report distinguishes:

```text
Documented:
- ...

Upstream background (not an ECNU guarantee):
- ...

Observed on YYYY-MM-DD:
- ...

Unverified or environment-limited:
- ...

Recommended application policy:
- ...
```

This prevents application safeguards and one-time observations from being
mistaken for platform guarantees.
