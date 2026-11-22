# Troubleshooting and live checks

Fix the failing integration with the smallest change; do not audit every
endpoint. Capture only the endpoint, model, SDK version, status, content type,
request ID and a bounded, redacted error sample. Never capture credentials,
private prompts or reasoning.

## Start from the symptom

The **Evidence** column says where a row comes from: the official docs, or a
live observation with its date (Asia/Shanghai, ECNU's time zone; runner
reports use UTC) and the [runner case](#run-a-live-check) that reproduces it. Observations are not guarantees; any ECNU release can change
them, so rerun the case before relying on an old one.

| Symptom | What is happening and what to do | Evidence |
|---|---|---|
| `401` for one model name only | Unsupported model names return `401` "获取第三方元数据失败". Check the name against the [model list](models.md#current-model-snapshot) before rotating the key | 2026-11-23 `error_unsupported_model` |
| `401` with an Anthropic client that appends `[1m]` | The docs retired the suffix and say unknown names map to `ecnu-plus`, but it returns `401` instead; use plain `ecnu-max` | 2026-11-23 `anthropic_max_1m` |
| `401` from `ecnu-decision` | The token may not have the model assigned | docs |
| Plain-text `500` after setting `reasoning_effort` | Unsupported tier for that model, not an outage: `ecnu-plus` rejects `high` (and `minimal`, `max`) this way. Validate tiers per model | 2026-11-23 `effort_unsupported_ecnu_plus` |
| An undocumented effort tier works on `ecnu-max` | `medium` (also `minimal`, `xhigh`) is accepted; the applied tier is unknown. Send only `low` / `high` / `max` | 2026-11-23 `effort_undocumented_ecnu_max` |
| Plain-text `500` for an invalid effort value on `ecnu-max` | Same validation gap; fix the value, do not retry | 2026-11-23 `chat_invalid_reasoning_effort` |
| Thinking runs and bills although `thinking` was not sent | `reasoning_effort` alone enables thinking on both models; omit it when thinking should be off | 2026-11-23 `effort_only_ecnu_max`, `effort_only_ecnu_plus` |
| `reasoning_content` missing although thinking seems on | Fields and counters vary; see [usage fields](engineering.md#responses-you-should-not-over-trust) | 2026-11-23 `chat_thinking_tool_continue` |
| Embedding input over 8192 characters succeeds | The limit is not enforced and truncation cannot be ruled out; chunk locally | 2026-11-23 `embedding_8193_chars` |
| Rerank document over 8192 characters succeeds | Same; rerank chunks, not whole long documents | 2026-11-23 `rerank_document_8193` |
| `temperature` above 1 succeeds | Not validated; the applied value is unknown. Keep it in 0–1 | 2026-11-23 `error_unsupported_parameter_value` |
| TTS error handling crashes | An invalid voice returns `500 text/plain`; parse errors without assuming JSON and validate voices | 2026-11-23 `tts_invalid_voice` |
| PCM audio cannot be decoded | No `Content-Disposition` or PCM format headers are sent; configure rate, channels and bit depth in the client | 2026-11-23 `tts_xiayu_pcm` |
| A generated image URL cannot be fetched server-side | The URL host did not resolve only to public addresses; request `b64_json` instead | 2026-11-23 `image_generation_documented` (inconclusive) |
| `/models` lists an ID with no documentation | `ecnu-music` is visible but undocumented; use documented models only | 2026-11-23 `models_valid` |
| Embeddings via the OpenAI SDK look like strings | The SDK requests `encoding_format=base64` and the service honors it; the SDK decodes it, raw HTTP callers must | 2026-11-23 `openai_sdk_embedding` |
| `ecnu-decision` returns `400` or `422` | Unsupported question option, `bool` instead of `noul`, or context overflow; bodies use `detail` or `error` | docs, 2026-11-23 `decision_bool_type` |
| `403` "IP … 不在白名单中" | The client IP is not on the allowlist; a new server needs its egress IP approved | docs |
| `422` | Request validation failed; read `detail` and fix the request | docs |
| `429` | Per-model concurrency cap or exhausted 7-day quota; see [concurrency](engineering.md#concurrency) | docs |
| Timeout or dropped connection after a POST | Completion and charge are unknown; follow the [retry table](engineering.md#retries-follow-side-effects-not-status-codes) | docs |

## Run a live check

`scripts/smoke_test.py` in this skill's directory runs named cases serially,
with POST retries disabled, credits reserved before each request, and reports
reduced to structure and usage. It reads only `ECNU_API_KEY`. Check current
prices first; token estimates use off-peak rates.

Use whichever Python launcher the machine has (`python3`, `python`, `py`, or
`uv run --no-project python`); `python3` is often missing on Windows.

```bash
python scripts/smoke_test.py --help
python scripts/smoke_test.py --profile core --case models_valid --case effort_only_ecnu_plus --max-credits 1 --output .live-artifacts/check.json
```

Pick the case from the Evidence column, or a profile: `auth` (GET only),
`core`, `compatibility`, `billable` (image and TTS), or `all`. The default
50-credit ceiling is a cap, not authorization; keep one cumulative allowance
across reruns. Image and TTS cases need explicit authorization for those charges.

| Result | Meaning |
|---|---|
| `pass` | The response matched the documented expectation |
| `mismatch` | The service differs from the docs; for the cases above this means the deviation is still present |
| `inconclusive` | No supportable conclusion, such as a transport failure |
| `skipped` | No request ran |

Keep reports under the ignored `.live-artifacts/` directory.

## Keeping this page current

Latest revalidation: 2026-11-23 Asia/Shanghai (runner reports from
2026-11-22T17:18Z onward), every linked official page reread, a full
`--profile all` run plus the cases above,
Windows 11 x64, Python 3.14, OpenAI 3.57, Anthropic 2.12, langchain-openai 1.8.5.
After an ECNU release, rerun `--profile all`: delete rows whose case now
passes, update dates of rows that still mismatch, and add a runner case before
adding any new observed row.
