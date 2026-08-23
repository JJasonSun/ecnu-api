# Known Service Deviations

These entries are point-in-time observations, not official contracts. Preserve
the documented expectation in `api_reference.md`. Do not change a test date or
status unless the behavior was actually exercised again.

Test environment `live-2026-08-23-a` was a personal token on macOS arm64
(Darwin 25.6.0), Python 3.9.6, OpenAI 2.48.0, Anthropic 0.125.0,
langchain-openai 0.3.35, httpx 0.28.1, direct HTTP where noted, and UTC report
timestamps. No private input or generated content was retained.

## Invalid bearer on model discovery

- **Tested at:** 2026-08-23
- **Environment:** live-2026-08-23-a, direct HTTP
- **Protocol and endpoint:** OpenAI-compatible `GET /models`
- **Documented expectation:** Missing or invalid authentication returns `401`.
- **Observed behavior:** An obviously invalid bearer returned `200` JSON with an empty model list.
- **Reproduction conditions:** Send `GET /models` with a non-secret invalid bearer value.
- **Impact:** An empty list can be mistaken for authenticated discovery.
- **Recommended fallback:** Require a non-empty valid-token list; do not use an empty list as an auth check.
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

- **Tested at:** 2026-08-23
- **Environment:** live-2026-08-23-a, direct HTTP
- **Protocol and endpoint:** OpenAI-compatible `POST /chat/completions`
- **Documented expectation:** `ecnu-max` does not support vision; use `ecnu-plus`.
- **Observed behavior:** A tiny PNG data URL sent directly to `ecnu-max` returned plain-text `500`; the `ecnu-plus` control returned `200` and recognized the image.
- **Reproduction conditions:** Send the same synthetic red-square image to each primary model.
- **Impact:** Direct unsupported vision fails without a structured validation body.
- **Recommended fallback:** Route all image understanding to `ecnu-plus` before sending.
- **Status:** active

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

## Update rules

1. Record the date, non-secret environment, protocol, endpoint, expectation,
   observed structure, reproduction conditions, impact, and fallback.
2. Use only `active`, `resolved`, `inconclusive`, or `not-retested` as status.
3. Remove keys, prompts, generated content, one-time URLs, and reasoning text.
4. Do not mark an item resolved from an unrelated success or an unexecuted case.
