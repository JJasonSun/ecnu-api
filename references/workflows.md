# Targeted diagnosis and live checks

Use this reference for a failure or an explicitly needed verification, not
as a prerequisite for normal implementation. Fix the requested integration;
do not audit every endpoint or run repository-maintainer checks in a business
project. Preserve a working framework and make the smallest relevant change.

## Start from the symptom

Capture only the endpoint, model, SDK/version, status, content type, request ID,
and a bounded redacted error sample. Never capture credentials, private prompts,
or reasoning. Read the matching section below, not the entire deviation log.
These links are dated observations, not claims that the issue still reproduces.

| Symptom | Check / relevant evidence |
|---|---|
| `200` with an empty model list | Not proof of authentication: [invalid bearer](known_deviations.md#invalid-bearer-on-model-discovery) |
| Missing auth produces an unexpected error | Preserve actual status and body type: [missing authorization](known_deviations.md#missing-authorization-on-model-discovery) |
| A new model ID appears but fails | Discovery is not endpoint capability: [runtime-only model](known_deviations.md#undocumented-model-visible-at-runtime) |
| `401` only for an unsupported model or `[1m]` | Compare a documented working control; do not rotate keys blindly: [unsupported model](known_deviations.md#unsupported-chat-model-error), [suffix conditions](known_deviations.md#anthropic-long-context-suffix-metadata) |
| SDK works for chat but embeddings fail | Check raw strings and local validation: [embedding recipe](examples.md#langchain-embeddings) |
| Tool continuation loses state or reasoning fields | Preserve the actual message and inspect serialization: [recipe](examples.md#thinking-and-tool-history), [field variation](known_deviations.md#max-thinking-response-fields) |
| TTS error parsing crashes | Tolerate non-JSON errors: [invalid voice](known_deviations.md#invalid-tts-voice-error-shape) |
| PCM bytes arrive without format metadata | Configure the format explicitly: [missing headers](known_deviations.md#successful-tts-response-headers) |
| Historical max-vision limitation conflicts with current docs | Check the chosen protocol and current contract: [resolved fixture](known_deviations.md#direct-ecnu-max-image-input) |
| `422` | Inspect `detail` and the relevant [request contract](api_reference.md); do not retry the unchanged request |
| `429` | Check [current credits/quota](models.md); stop parallel retries |
| Timeout or dropped connection after POST | Completion and debit may be unknown; do not automatically resubmit |

A later release announcement does not by itself resolve a deviation. Do not
change observation dates or statuses without reproducing the affected behavior.

## Run only the check needed

If execution is not authorized or the key is absent, continue offline diagnosis
and provide the smallest runnable check. Do not repeatedly ask for authorization
already covering this account, data, destination, purpose, and cumulative budget.
New scope or an explicit per-action approval requirement still needs approval.

For authorized live checks, use the existing `scripts/smoke_test.py` from the
installed skill's directory, not an assumed script in the user's application.
Check current prices first. The runner reads only `ECNU_API_KEY`, runs serially,
disables POST retries, reserves estimated credits, and redacts reports. Its
50-credit default is a cap, not authorization; use the lower approved cap and
obtain separate authorization before exceeding 50. Estimates are not actual debit.
Keep the same cumulative allowance across reruns, not a new allowance per process.

To inspect options without a network request:

```bash
python3 scripts/smoke_test.py --help
```

After approval for a model-list check and one SDK chat probe, with current
estimated cost within the approved allowance, an example targeted invocation is:

```bash
python3 scripts/smoke_test.py --profile core   --case models_valid --case openai_sdk_chat   --max-credits 1 --output .live-artifacts/openai-sdk-chat.json
```

The example ceiling is not a current price quote or spending permission.
Choose an actual case that answers the user's question. `auth` performs GET
checks only but is not conclusive authentication proof; `core`, `compatibility`,
and `billable` group other probes. Use `--case` to narrow them. Do not use `all`
for an ordinary integration check. Image/TTS probes need authorization covering
those billable operations and must not be scheduled automatically.

## Interpret the evidence

| Runner result | Meaning |
|---|---|
| `pass` | That case's checks passed in this dated environment, not universal task quality |
| `mismatch` | The observed response differs from the checked expectation |
| `inconclusive` | No supportable conclusion, including a transport failure |
| `skipped` | No request ran; no live evidence |

Keep reports under ignored `.live-artifacts/`. Report what was actually run and
what remains unknown; a failed download does not authorize another paid generation.
For a suffix fallback, retain the exact working-control and consent conditions in
the linked deviation rather than silently downgrading the capability.
