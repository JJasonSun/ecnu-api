# Known Service Deviations

These entries are point-in-time observations, not official contracts. Keep each
entry's documented expectation separate from its observed result; current
contracts are linked from [api_reference.md](api_reference.md). Do not change a
test date or status unless the behavior was actually exercised again.

Test environment `live-2026-08-23-a` was a personal token on macOS arm64
(Darwin 25.6.0), Python 3.9.6, OpenAI 2.48.0, Anthropic 0.125.0,
langchain-openai 0.3.35, httpx 0.28.1, direct HTTP where noted, and UTC report
timestamps. No private input or generated content was retained.

Test environment `live-2026-09-12-a` used the account owner's test token,
macOS arm64, Python 3.9.6, and direct standard-library HTTP through the smoke
runner. The date is Asia/Shanghai; sanitized reports use UTC timestamps.
Requests were serial with no POST retries and a cumulative 50-credit ceiling.
Only synthetic text and PNG inputs were used. Prompts, generated content,
reasoning text, and credentials were not retained in reports.

Test environment `live-2026-09-12-b` checked the PR #3 recipes with the same
macOS/Python environment, OpenAI 2.48.0, Anthropic 0.125.0,
langchain-openai 0.3.35, and httpx 0.28.1. Requests used synthetic text,
60-second timeouts, no retries, and the same cumulative 50-credit ceiling.
Only response structure, field-preservation checks, and usage were retained.

Test environment `live-2026-09-12-c` used the account owner's personal tokens
(two distinct keys), Windows x64, Node.js 24.14.1 `fetch` direct HTTP, and
Asia/Shanghai local dates 2026-09-12 through 2026-09-14, during an
owner-authorized interactive integration session rather than the smoke runner.
Reliability runs were serial with roughly four-second spacing; unspaced bursts
are called out per entry. Repeated attempts in those runs were deliberate
characterization samples, not uncertainty retries, and credit consumption was
not metered against the runner's ceiling. Only synthetic arithmetic and
vision-fixture inputs were used. Prompts, generated content, reasoning text,
and credentials were not retained.

## Invalid bearer on model discovery

- **Tested at:** 2026-08-23; reproduced 2026-09-12
- **Environment:** live-2026-08-23-a, direct HTTP; live-2026-09-12-b, HTTPX
- **Protocol and endpoint:** OpenAI-compatible `GET /models`
- **Documented expectation:** Missing or invalid authentication returns `401`.
- **Observed behavior:** An obviously invalid bearer returned `200` JSON with an empty model list.
- **Reproduction conditions:** Send `GET /models` with a non-secret invalid bearer value.
- **Impact:** An empty list can be mistaken for authenticated discovery.
- **Recommended fallback:** Treat discovery as model visibility, not authentication proof; check authenticated access with a protected documented endpoint.
- **Status:** active

## Missing authorization on model discovery

- **Tested at:** 2026-08-23
- **Environment:** live-2026-08-23-a, direct HTTP
- **Protocol and endpoint:** OpenAI-compatible `GET /models`
- **Documented expectation:** Missing authentication returns `401`.
- **Observed behavior:** The response was `500 application/json` with an HTML 500 page stored in the JSON `error` string.
- **Reproduction conditions:** Send `GET /models` without an Authorization header.
- **Impact:** Status-only or HTML-only handling can misclassify the failure.
- **Recommended fallback:** Preserve status, content type, request ID, and a bounded redacted body sample.
- **Status:** active

## Undocumented model visible at runtime

- **Tested at:** 2026-08-23
- **Environment:** live-2026-08-23-a, direct HTTP
- **Protocol and endpoint:** OpenAI-compatible `GET /models`
- **Documented expectation:** Runtime discovery is interpreted with the current model page.
- **Observed behavior:** The seven-model list included `ecnu-image-pro`, which was absent from the model page.
- **Reproduction conditions:** Compare a valid-token model list with the current official model page.
- **Impact:** Visibility alone may lead callers to select an undocumented ID.
- **Recommended fallback:** Classify it as visible-but-undocumented and do not select it without an authorized endpoint probe.
- **Status:** active

## Undocumented image model generation

- **Tested at:** 2026-08-21
- **Environment:** Personal token; exact OS, Python, SDK, and transport versions were not recorded.
- **Protocol and endpoint:** OpenAI-compatible `POST /images/generations`
- **Documented expectation:** `ecnu-image-pro` has no documented generation contract.
- **Observed behavior:** One probe returned plain-text `500 Internal Server Error`.
- **Reproduction conditions:** Submit one minimal request using the runtime-only model ID.
- **Impact:** A visible ID was not verifiably usable and the POST may have cost implications.
- **Recommended fallback:** Use documented `ecnu-image`; do not retry or routinely probe undocumented image models.
- **Status:** not-retested

## Invalid TTS voice error shape

- **Tested at:** 2026-08-23
- **Environment:** live-2026-08-23-a, direct HTTP
- **Protocol and endpoint:** OpenAI-compatible `POST /audio/speech`
- **Documented expectation:** Invalid voice input returns `400` JSON with `error`, `request_id`, and `details`.
- **Observed behavior:** An invalid voice returned `500 text/plain` with a bounded internal-error string.
- **Reproduction conditions:** Submit the short text `你好。` with an obviously invalid voice ID.
- **Impact:** Clients cannot rely on the documented JSON voice list.
- **Recommended fallback:** Tolerate non-JSON errors and retain only a bounded redacted sample.
- **Status:** active

## Successful TTS response headers

- **Tested at:** 2026-08-23
- **Environment:** live-2026-08-23-a, direct HTTP
- **Protocol and endpoint:** OpenAI-compatible `POST /audio/speech`
- **Documented expectation:** Successful audio includes `Content-Disposition`; PCM also includes rate, channel, and bit-depth headers.
- **Observed behavior:** Short `xiayu` PCM and MP3 returned non-empty audio-typed bodies but no `Content-Disposition`; PCM also omitted all three format headers.
- **Reproduction conditions:** Request `你好。` with `xiayu` as PCM and MP3 in separate sequential calls.
- **Impact:** Callers cannot derive filenames or raw PCM configuration from the response.
- **Recommended fallback:** Validate MIME and bytes, choose a local filename, and configure PCM explicitly when headers are absent.
- **Status:** active

## Anthropic long-context suffix metadata

- **Tested at:** 2026-08-23
- **Environment:** live-2026-08-23-a, direct HTTP with Bearer auth
- **Protocol and endpoint:** Anthropic-compatible `POST /v1/messages`
- **Documented expectation:** The proxy strips `[1m]`, routes to `ecnu-max`, and advertises 1M-character context.
- **Observed behavior:** `ecnu-max[1m]` returned metadata-related `401`; the immediate plain `ecnu-max` control returned `200`.
- **Reproduction conditions:** Compare otherwise identical short requests for suffixed and plain model names.
- **Impact:** Model access can work while the long-context compatibility signal fails.
- **Recommended fallback:** Only after the same credential has passed a plain `ecnu-max` control, fall back once when the suffix returns this exact metadata-related `401`; disclose the loss of the 1M signal and require the caller to accept it.
- **Status:** active

## Anthropic effort `none`

- **Tested at:** 2026-08-23
- **Environment:** live-2026-08-23-a, direct HTTP with Bearer auth
- **Protocol and endpoint:** Anthropic-compatible `POST /v1/messages`
- **Documented expectation:** `output_config.effort: none` disables thinking.
- **Observed behavior:** The request returned structured `422`; the accepted-value message listed `low`, `medium`, `high`, `xhigh`, and `max` only.
- **Reproduction conditions:** Send a short `ecnu-max` request with effort `none`.
- **Impact:** Clients following the documented disable value fail validation.
- **Recommended fallback:** Omit `output_config` when thinking is not required; do not translate `none` into a supported tier silently.
- **Status:** active

## Empty embedding array error

- **Tested at:** 2026-08-23
- **Environment:** live-2026-08-23-a, direct HTTP
- **Protocol and endpoint:** OpenAI-compatible `POST /embeddings`
- **Documented expectation:** `input` is a string or string array; invalid request shapes use structured validation errors.
- **Observed behavior:** An empty string array returned plain-text `500 Internal Server Error`.
- **Reproduction conditions:** Send `input: []` with `ecnu-embedding-small`.
- **Impact:** A deterministic client error appears as a server failure.
- **Recommended fallback:** Reject empty arrays locally and do not retry the unchanged POST.
- **Status:** active

## Embedding 8192-character boundary

- **Tested at:** 2026-08-23
- **Environment:** live-2026-08-23-a, direct HTTP
- **Protocol and endpoint:** OpenAI-compatible `POST /embeddings`
- **Documented expectation:** Input is limited to 8192 characters.
- **Observed behavior:** Both 8192 and 8193 ASCII characters returned `200` with one 1024-value vector.
- **Reproduction conditions:** Send separate scalar inputs of exactly 8192 and 8193 characters.
- **Impact:** The documented boundary was not enforced by this deployment.
- **Recommended fallback:** Continue enforcing 8192 characters in clients; do not promote one accepted over-limit request into a new limit.
- **Status:** active

## Rerank document 8192-character boundary

- **Tested at:** 2026-08-23
- **Environment:** live-2026-08-23-a, direct HTTP
- **Protocol and endpoint:** Cohere-compatible `POST /rerank`
- **Documented expectation:** Each document is limited to 8192 characters.
- **Observed behavior:** A single 8193-character document returned `200` with a scored result.
- **Reproduction conditions:** Rerank one 8193-character document against a short query.
- **Impact:** The documented boundary was not enforced by this deployment.
- **Recommended fallback:** Keep the documented 8192-character client guard.
- **Status:** active

## Invalid Chat reasoning effort error

- **Tested at:** 2026-08-23
- **Environment:** live-2026-08-23-a, direct HTTP
- **Protocol and endpoint:** OpenAI-compatible `POST /chat/completions`
- **Documented expectation:** Direct `reasoning_effort` accepts `low`, `high`, or `max`; invalid fields normally produce structured validation errors.
- **Observed behavior:** An invalid value returned plain-text `500 Internal Server Error`.
- **Reproduction conditions:** Enable thinking for `ecnu-max` and send an obviously invalid effort value.
- **Impact:** Callers cannot inspect a field path or accepted values.
- **Recommended fallback:** Validate the three documented values locally and never retry the same invalid request.
- **Status:** active

## Out-of-range Chat temperature

- **Tested at:** 2026-08-23
- **Environment:** live-2026-08-23-a, direct HTTP
- **Protocol and endpoint:** OpenAI-compatible `POST /chat/completions`
- **Documented expectation:** `temperature` is between 0 and 1.
- **Observed behavior:** A short `ecnu-plus` request with `temperature: 2` returned `200` and a normal completion shape.
- **Reproduction conditions:** Send the otherwise minimal deterministic Chat request with temperature 2.
- **Impact:** Current server acceptance can hide invalid application configuration.
- **Recommended fallback:** Enforce the documented range client-side.
- **Status:** active

## Unsupported Chat model error

- **Tested at:** 2026-08-23
- **Environment:** live-2026-08-23-a, direct HTTP
- **Protocol and endpoint:** OpenAI-compatible `POST /chat/completions`
- **Documented expectation:** `401` indicates credential failure; unsupported request values should not be confused with invalid bearer auth.
- **Observed behavior:** An obviously unsupported model returned `401` JSON indicating third-party metadata retrieval failure while the same bearer passed `/models` and primary-model calls.
- **Reproduction conditions:** Use a valid bearer with a synthetic unsupported model name.
- **Impact:** A model-resolution failure can trigger incorrect credential rotation or a global auth stop.
- **Recommended fallback:** Verify auth with a documented model; treat this 401 as case-specific after a valid control succeeds.
- **Status:** active

## Direct `ecnu-max` image input

- **Tested at:** 2026-09-12; previous failure on 2026-08-23
- **Environment:** live-2026-09-12-a, direct HTTP; historical live-2026-08-23-a
- **Protocol and endpoint:** OpenAI-compatible `POST /chat/completions`
- **Documented expectation:** Current model and Chat Completions pages support image input on both primary models. The August contract did not support it on `ecnu-max`.
- **Observed behavior:** Both models returned `200`, ended normally, and recognized a synthetic red square. The earlier max plain-text `500` is historical. A plus probe limited to 32 output tokens was truncated; a separate 128-token probe completed and recognized the image.
- **Reproduction conditions:** Send the same tiny PNG data URL to each model with `max_tokens: 128`; require a normal completion and correct visible content.
- **Impact:** The old max failure no longer reproduces for this fixture. Too little output budget can make a vision check inconclusive or misleading.
- **Recommended fallback:** Budget complete output and validate image-grounded behavior; this simple fixture does not establish OCR or complex visual reasoning quality.
- **Status:** resolved

## Max thinking response fields

- **Tested at:** 2026-09-12
- **Environment:** live-2026-09-12-a, direct HTTP
- **Protocol and endpoint:** OpenAI-compatible `POST /chat/completions`
- **Documented expectation:** Enabled thinking exposes `reasoning_content`; thinking tool history retains that field. Max accepts `low`, `high`, and `max` effort.
- **Observed behavior:** All three effort values returned `200` with reported reasoning-token usage, but those replies and a tool-call reply lacked `reasoning_content`. A later complex max tool reply included a separate `reasoning` key; its content was not inspected or retained. Preserving the complete actual message allowed the tool continuation and a later user turn to succeed. A separate max coding fixture did return `reasoning_content`, so field exposure varied across replies.
- **Reproduction conditions:** Enable thinking, submit a short task with each documented effort, then run a bounded echo tool exchange and a later user turn with the original messages preserved. Record field presence and usage counters only.
- **Impact:** Requiring one field name can block a working tool loop. Its absence does not prove thinking was disabled; this run does not establish the tiers' relative quality or latency.
- **Recommended fallback:** Preserve the complete returned assistant message in memory; retain `reasoning_content` when supplied and never fabricate it when absent. Redact both `reasoning_content` and `reasoning` from diagnostics. Validate SDK and framework continuation separately.
- **Status:** active

## Initial max Chat timeout

- **Tested at:** 2026-09-12
- **Environment:** live-2026-09-12-a, direct HTTP
- **Protocol and endpoint:** OpenAI-compatible `POST /chat/completions`
- **Documented expectation:** A valid short request produces a completion; no latency guarantee was assumed.
- **Observed behavior:** The initial max basic request exceeded its 45-second client timeout with no HTTP response. It was not retried. Subsequent independent max fixtures completed successfully.
- **Reproduction conditions:** One minimal non-thinking max request with a 45-second timeout; the timeout itself has not been reproduced.
- **Impact:** Completion and debit for that request remain unknown. A single timeout does not establish a service-wide outage.
- **Recommended fallback:** Keep the attempt inconclusive, inspect available status or request records, and avoid blindly repeating a possibly billed POST.
- **Status:** inconclusive

## Thinking-tool continuation without reasoning content

- **Tested at:** 2026-08-23
- **Environment:** live-2026-08-23-a, direct HTTP
- **Protocol and endpoint:** OpenAI-compatible `POST /chat/completions`
- **Documented expectation:** A thinking-mode assistant tool call must retain `reasoning_content` in subsequent turns.
- **Observed behavior:** The correct preserved-reasoning flow returned `200`, and a single negative continuation with the field omitted also returned `200`.
- **Reproduction conditions:** Reuse one deterministic `echo` tool call, then submit preserved and omitted variants once each.
- **Impact:** Current permissive behavior can hide a client bug that may fail on another model or deployment.
- **Recommended fallback:** Continue preserving the field ephemerally; never rely on the observed permissiveness.
- **Status:** active

## Generated image URL verification

- **Tested at:** 2026-08-23
- **Environment:** live-2026-08-23-a, direct HTTP plus bounded safe downloader
- **Protocol and endpoint:** OpenAI-compatible `POST /images/generations`
- **Documented expectation:** A documented `ecnu-image` URL result is available for transfer for 24 hours.
- **Observed behavior:** The single generation returned `200` with a URL, but its host did not resolve exclusively to public IP addresses, so the low-risk downloader refused access and no image bytes were retained.
- **Reproduction conditions:** Generate one 512x512 URL result and apply public-HTTPS DNS and redirect checks before download.
- **Impact:** Content type, byte hash, and pixel dimensions could not be verified without relaxing the safety policy or paying for another generation.
- **Recommended fallback:** Treat the generation as inconclusive; transfer through an approved network path and never blindly retry the POST.
- **Status:** inconclusive

## Verified coverage on 2026-08-23

Across the 2026-08-23 runs and targeted reruns, the probes successfully checked
valid model discovery; direct and OpenAI-SDK Chat; bounded SSE with empty chunks
and `[DONE]`; `ecnu-max` thinking low;
deterministic tools and the correct two-turn thinking-tool splice; Responses
with effort `none` and `low`; scalar, array, SDK, and LangChain embeddings;
integer-token rejection; standard rerank behavior; `ecnu-plus` vision; JSON
Schema structure; Anthropic direct names, alias requests, valid effort, plain-max
fallback, and SDK use; and image stripping in the Responses and Anthropic
compatibility layers. Successful Chat responses may expose backend model labels,
while Anthropic alias responses may echo the requested alias; neither label alone
proves or disproves internal routing.

## Verified coverage on 2026-09-12

Environment `live-2026-09-12-a` made 30 requests: 24 passed their checks, five differed
from expectations, and one timed out. The five mismatches were the four
canonical reasoning-field checks described above and the truncated plus image
probe. The latter was followed by a normally completed image check with more
output room; the timeout was not retried.

Successful coverage included:

- Both primary models recognized the actual synthetic image and returned valid
  `json_schema` and `json_object` output.
- Max image input also worked through the Responses and Anthropic endpoints
  for this fixture. This remains observed compatibility, not a documented
  general image-input contract for those protocols.
- The exact system prompt in `agent_development.md` completed an echo tool
  exchange and a later user turn on both models. Plus retained canonical
  reasoning content; max retained all actual returned fields. A separate max
  non-thinking tool exchange also passed.
- Both models extracted the requested fields while ignoring conflicting
  instructions inside one synthetic untrusted source. One success is not a
  prompt-injection resistance guarantee.
- Both models used the exact coding prompt template plus a supplied small
  Python fixture to propose a fix. A restricted in-memory check verified empty,
  ordinary, zero, and empty-string inputs. Plus used thinking off; max used low.
  This is a small prompt check, not a repository-level coding benchmark.
- A constrained arithmetic task with max effort returned the expected answer
  and reported reasoning-token usage; visible reasoning was not a pass criterion.

The cumulative reserved estimate was 37.74 credits, within the 50-credit
ceiling. Usage-based estimated consumption was 3.49058 credits, including the
runner's reservation fallback for the timeout; this is not a verified debit.
No live SDK, streaming, long-context, media-generation, embedding, or rerank
revalidation was performed in this update. Older observations retain their
original dates.

Response model metadata included `qwen3.6-plus`, `deepseek-v4-flash`, and
`deepseek-flash`, differing from the current model page's labels. These values
alone do not establish the deployed model identity or contradict its documented
routing; do not silently replace the documented model table with them.

## Verified recipe coverage on 2026-09-12

Environment `live-2026-09-12-b` made eight requests: six POSTs and two GETs.
Seven passed their checks; the invalid-bearer GET reproduced the `200` empty-list
deviation above. Every request had exactly one transport attempt.

- The exact Python Chat and Anthropic SDK snippets returned normally completed text.
- The LangChain snippet sent both original strings, omitted `dimensions`, and
  included the SDK's automatic `encoding_format="base64"`. The service accepted
  this request and returned two 1024-value vectors.
- Max thinking at `low` returned an echo tool call with `reasoning_content`.
  The SDK recipe's dictionary equaled the original response message. The tool
  result and later user turn both preserved that original message on the wire
  and returned the expected value with normal completion.

This batch's usage-based estimate was 0.43764 credits under the
[current pricing formula](https://developer.ecnu.edu.cn/vitepress/llm/limit.html).
The cumulative reservation, including earlier checks, was 44.29 credits;
estimated cumulative consumption was 3.92822 credits. Neither is verified
account debit. This targeted run does not revalidate other historical cases,
other SDK versions, streaming, or arbitrary framework adapters.

## ecnu-reasoner alias default thinking

- **Tested at:** 2026-09-12
- **Environment:** live-2026-09-12-c, Node.js `fetch` direct HTTP
- **Protocol and endpoint:** OpenAI-compatible `POST /chat/completions`
- **Documented expectation:** The alias `ecnu-reasoner` equals `ecnu-max` with `thinking: {"type": "enabled"}`; a client must send the `thinking` parameter to activate thinking on `ecnu-max` itself.
- **Observed behavior:** A bare `ecnu-reasoner` request with no `thinking` field returned `200` and a non-zero `usage.completion_tokens_details.reasoning_tokens` count (range 18-198 across samples). A matching bare `ecnu-max` control returned `reasoning_tokens: 0`. The alias activates thinking server-side without any client-side `thinking` parameter.
- **Reproduction conditions:** Send two otherwise identical minimal requests, one with `model: "ecnu-reasoner"` and one with `model: "ecnu-max"`, both omitting `thinking`; compare `usage.completion_tokens_details.reasoning_tokens`.
- **Impact:** A client that relies on sending `thinking` to detect whether reasoning is active will misclassify `ecnu-reasoner` responses. The absence of `message.reasoning_content` is not a reliable thinking indicator either (see the prior "Max thinking response fields" entry).
- **Recommended fallback:** Detect active thinking via `usage.completion_tokens_details.reasoning_tokens`, not via `message.reasoning_content` or the presence of a client-side `thinking` parameter. Treat `ecnu-reasoner` as always-thinking for routing decisions.
- **Status:** active

## ecnu-max reasoning_effort as thinking trigger

- **Tested at:** 2026-09-12
- **Environment:** live-2026-09-12-c, Node.js `fetch` direct HTTP
- **Protocol and endpoint:** OpenAI-compatible `POST /chat/completions`
- **Documented expectation:** The thinking page states that `reasoning_effort` only takes effect when thinking mode is enabled via `thinking: {"type": "enabled"}`; without it, `reasoning_effort` is ignored.
- **Observed behavior:** `ecnu-max` requests with `reasoning_effort` set but no `thinking` field returned `200` with non-zero `usage.completion_tokens_details.reasoning_tokens`. Dose-response was clean across `low` (median ~117), `high` (~155), and `max` (~343). Adding `thinking: {"type": "enabled"}` alongside `reasoning_effort` did not increase the token count beyond the same-effort baseline.
- **Reproduction conditions:** Send `ecnu-max` requests with `reasoning_effort` set to `low`, `high`, and `max` but omit `thinking`; record `usage.completion_tokens_details.reasoning_tokens` for each.
- **Impact:** Clients following the documented precondition may unnecessarily send a `thinking` parameter, or may wrongly conclude thinking is off when only `reasoning_effort` is sent. The documented gating does not match the current deployment.
- **Recommended fallback:** For `ecnu-max`, sending `reasoning_effort` alone is sufficient to activate thinking; the `thinking` parameter is optional. Do not treat the documented gating as authoritative until rechecked. Keep the `thinking` parameter if an upstream SDK requires it, but do not require it for function.
- **Status:** active

## Unavailable reasoning effort tiers

- **Tested at:** 2026-09-12
- **Environment:** live-2026-09-12-c, Node.js `fetch` direct HTTP
- **Protocol and endpoint:** OpenAI-compatible `POST /chat/completions`
- **Documented expectation:** The thinking page lists `low`, `high`, and `max` as the three supported `reasoning_effort` values for `ecnu-max`.
- **Observed behavior:** `minimal` returned HTTP 500 on 5 of 7 attempts; `medium` returned HTTP 500 on 7 of 9 attempts. Both occasionally succeeded but cannot be relied on. `xhigh`, although absent from the documentation, returned `200` on all attempts with a reasoning-token median (~178) between `high` and `max`. `low`, `high`, and `max` were stable across all samples.
- **Reproduction conditions:** Send `ecnu-max` requests with each of `minimal`, `medium`, `xhigh`, `low`, `high`, and `max` as `reasoning_effort`; use serial requests with roughly four-second spacing to avoid the rate-limit deviation below.
- **Impact:** A client that sends `minimal` or `medium` (for example, via an SDK default or a UI selector that does not filter values) will hit intermittent 500 errors. `xhigh` is a usable but undocumented tier.
- **Recommended fallback:** Restrict `reasoning_effort` to `low`, `high`, `xhigh`, and `max` in client-side selectors and validators. Do not send `minimal` or `medium`. If an SDK or framework injects those values, intercept and remap them before the request. Treat `xhigh` as usable but recheck before relying on it for a production default.
- **Status:** active

## Rapid-request 401 metadata failure

- **Tested at:** 2026-09-12
- **Environment:** live-2026-09-12-c, Node.js `fetch` direct HTTP
- **Protocol and endpoint:** OpenAI-compatible `POST /chat/completions` and `GET /models`
- **Documented expectation:** `401` indicates an authentication failure; the official guidance only advises avoiding parallel calls.
- **Observed behavior:** Rapid sequential requests (under roughly one second apart) to either endpoint returned `401` with `{"detail": "获取第三方元数据失败"}` even though the same bearer passed spaced requests. Spacing requests by roughly four seconds eliminated the failures. The error shape is identical to the unsupported-model case above, making them indistinguishable without a working control.
- **Reproduction conditions:** Send the same valid bearer to the same documented model in a tight loop (sub-second spacing); then repeat with four-second spacing.
- **Impact:** A client may mistake rate-limiting for a credential failure and trigger key rotation or an auth stop. A retry loop without backoff can sustain the 401 and exhaust credits on failed attempts.
- **Recommended fallback:** On a `401` with this detail string, first retry once after a four-second delay before treating it as an authentication failure. Always serialize requests to ECNU; do not use parallel call patterns. Do not rotate keys based solely on this error shape without a spaced-control request.
- **Status:** active

## Verified coverage on 2026-09-12 through 2026-09-14

Environment `live-2026-09-12-c` made characterization requests across two
personal tokens on Windows x64, Node.js 24.14.1, over Asia/Shanghai dates
2026-09-12 through 2026-09-14. Requests were serial with roughly four-second
spacing except where unspaced bursts are noted. No credit metering was applied;
this was an owner-authorized interactive session, not a smoke-runner batch.

Successful coverage included:

- Both `ecnu-max` and `ecnu-reasoner` returned `200` for `reasoning_effort`
  values `low`, `high`, `xhigh`, and `max`, with a clean dose-response curve
  (median reasoning tokens: low ~117, high ~155, xhigh ~178, max ~343).
- `ecnu-reasoner` bare requests returned non-zero reasoning tokens; `ecnu-max`
  bare requests returned zero. The alias activates thinking server-side.
- `ecnu-max` with `reasoning_effort` but no `thinking` parameter activated
  thinking, contradicting the documented gating.
- `minimal` and `medium` efforts returned intermittent HTTP 500 and are
  unreliable; `xhigh` is undocumented but stable.
- Both models correctly recognized a synthetic 96x96 red-circle PNG and
  returned the expected "circle red" description, with and without thinking.
- Function calling with thinking coexisted normally on both models; a
  two-turn tool exchange without preserved `reasoning_content` returned `200`.
- Rapid sub-second request bursts returned `401`
  `{"detail": "获取第三方元数据失败"}`; four-second spacing eliminated it.

No SDK, streaming, long-context, embedding, rerank, TTS, or image-generation
revalidation was performed in this run. The dose-response medians are
characterization samples, not quality benchmarks. Older observations retain
their original dates and statuses.

## Update rules

1. Record the date, non-secret environment, protocol, endpoint, expectation,
   observed structure, reproduction conditions, impact, and fallback.
2. Use only `active`, `resolved`, `inconclusive`, or `not-retested` as status.
3. Remove keys, prompts, generated content, one-time URLs, and reasoning text.
4. Do not mark an item resolved from an unrelated success or an unexecuted case.
5. Treat an ECNU release, model rollout, endpoint change, quota change, or
   announced fix as a revalidation trigger, not as resolution evidence.
6. Recheck the current contract and pricing, then rerun only the affected cases
   with the current runner before changing dates, expectations, or statuses.
7. Require scoped account-owner authorization for billable revalidation; never
   schedule TTS or image-generation probes automatically.
