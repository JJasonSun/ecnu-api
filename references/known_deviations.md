# Known Service Deviations

These are point-in-time observations from a personal-token test on
**2026-08-21**. They are not official contracts. Re-run a controlled smoke test
before relying on them, and update this file only when a result is actually
reproduced.

## Observation matrix

| Area | Documented expectation | Observed behavior | Application fallback |
|---|---|---|---|
| `/models`, invalid token | authentication error | `200` with an empty model list | never use an empty list as an authentication check |
| `/models`, missing auth | authentication error | `500` with an HTML error embedded in the response | preserve content type/body; report auth as inconclusive |
| runtime model list | documented models | included `ecnu-image-pro`, absent from model page | do not select undocumented IDs without an endpoint probe |
| `ecnu-image-pro` generation | not documented | probe returned plain-text `500` | use documented `ecnu-image` |
| TTS invalid voice | documented `400` JSON details | plain-text `500` | preserve status/content type; do not assume JSON |
| TTS PCM metadata | documented format metadata headers | `Content-Rate`, `Content-Channels`, and `Content-Bits` absent | inspect headers and require caller-side audio configuration |
| Anthropic `ecnu-max[1m]` | suffix stripped and long context advertised | `401` third-party metadata failure; plain `ecnu-max` worked | fall back to plain `ecnu-max` and report context-advertising difference |

## Verified in the same 2026-08-21 run

The repository maintainer recorded successful checks for:

- Chat Completions;
- thinking with `reasoning_effort`;
- non-tool multi-turn handling;
- tool calling;
- vision content parts;
- structured output;
- Responses API and `reasoning.effort`;
- scalar and array embeddings with 1024-value outputs;
- rerank;
- Anthropic model mapping and `output_config.effort`;
- documented image generation;
- default and additional TTS voices;
- `422` validation response shape.

These statements remain dated observations. They are not substitutes for
current production monitoring.

## How to update this file

1. Run a controlled authenticated test.
2. Record UTC date, account type, Python/SDK version, endpoint, status, content
   type, and structural result.
3. Remove keys, prompts, generated content, one-time URLs, and personal data.
4. Reproduce an anomaly before replacing an existing observation.
5. Keep the documented expectation in `api_reference.md`; keep only the
   deviation here.
6. Add or update an application fallback.
7. Do not write "fixed" merely because one subsequent request succeeded; note
   the evidence and date.
