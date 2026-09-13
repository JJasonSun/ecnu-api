# WorkBuddy desktop integration

Connect the ECNU Open Platform to the WorkBuddy desktop application (Tencent's
AI office workbench) as a custom OpenAI-compatible model source. This recipe
records the field-by-field configuration that passes WorkBuddy's validation and
survives its startup model-purge cycle. It is not a general Agent skill or a
WorkBuddy product guide.

## Configuration file

WorkBuddy reads custom models from `%USERPROFILE%\.workbuddy\models.json` on
Windows (or `~/.workbuddy/models.json` on macOS/Linux). The path can be
redirected via the `WORKBUDDY_CONFIG_DIR` environment variable.

The file **must be a top-level JSON array** of model objects, not the
`{"models": [...]}` object shape shown in the bundled CodeBuddy CLI
documentation. Two consumers share this file:

- The CLI custom-models provider reads it via `extractConfig`, which accepts
  either shape.
- The desktop local-model service reads it via `ModelsJsonStorage.update`,
  which treats the file as an array: `Array.isArray(current) ? [...current] : []`.
  On hardware-gate failure (CPU/GPU not in the whitelist), it rewrites the file
  unconditionally. An object-shaped file is collapsed to `[]` on every startup.

A bare array satisfies both: `extractConfig` returns `{models: parsed}` for an
array, and the purge's `filter(m => m?.local !== true)` preserves entries
without a `local` field. The `availableModels` field cannot be expressed in
array form; omit it to show all models.

Do not save from WorkBuddy's Settings → Custom Models editor: its save path
uses `parseModelsJson`, which does not accept arrays and will overwrite the
file with an object shape, which is then purged to `[]` on the next restart.
Edit the JSON file directly.

## Minimal working entry

```json
[
  {
    "id": "ecnu-reasoner",
    "name": "ECNU Max (thinking)",
    "vendor": "ECNU",
    "url": "https://chat.ecnu.edu.cn/open/api/v1/chat/completions",
    "apiKey": "sk-REDACTED",
    "maxInputTokens": 1000000,
    "maxOutputTokens": 65536,
    "supportsToolCall": true,
    "supportsImages": true,
    "supportsReasoning": true,
    "reasoning": {
      "defaultEffort": "max",
      "supportedEfforts": ["low", "high", "xhigh", "max"],
      "canDisableThinking": false
    },
    "relatedModels": {
      "lite": "ecnu-max",
      "reasoning": "ecnu-reasoner"
    },
    "onlyReasoning": true
  },
  {
    "id": "ecnu-max",
    "name": "ECNU Max",
    "vendor": "ECNU",
    "url": "https://chat.ecnu.edu.cn/open/api/v1/chat/completions",
    "apiKey": "sk-REDACTED",
    "maxInputTokens": 1000000,
    "maxOutputTokens": 65536,
    "supportsToolCall": true,
    "supportsImages": true,
    "supportsReasoning": true,
    "reasoning": {
      "defaultEffort": "max",
      "supportedEfforts": ["low", "high", "xhigh", "max"],
      "canDisableThinking": false
    },
    "relatedModels": {
      "lite": "ecnu-max",
      "reasoning": "ecnu-reasoner"
    },
    "onlyReasoning": true
  }
]
```

Never commit a real key. Store it in the file locally or reference an
environment variable via `"apiKey": "${ECNU_API_KEY}"`.

## Field notes

| Field | Value | Notes |
|---|---|---|
| `id` | `ecnu-max` / `ecnu-reasoner` | The id is also the `model` field sent to the API; do not change it to an upstream name like `deepseek-v4-flash`—ECNU rejects unknown ids with `{"detail":"获取第三方元数据失败"}`. |
| `url` | `…/v1/chat/completions` | Must end with `/chat/completions`. WorkBuddy auto-appends it unless `useCustomProtocol: true` is set. |
| `vendor` | `ECNU` or `Custom` | Cosmetic; does not affect routing. |
| `supportsReasoning` | `true` | Required for the effort selector and `/effort` command to appear. |
| `reasoning.defaultEffort` | `max` | The effort sent when no session or global override is set. |
| `reasoning.supportedEfforts` | `["low","high","xhigh","max"]` | Filters the UI selector and the `thinkingLevelMap`. Do not include `minimal` or `medium`—they return intermittent 500 ([observed](known_deviations.md#unavailable-reasoning-effort-tiers)). |
| `reasoning.canDisableThinking` | `false` | Both ECNU thinking models cannot disable thinking; this hides the "Off" entry in the selector. |
| `onlyReasoning` | `true` | Hides the "disable thinking" entry; matches the server-side behavior of `ecnu-reasoner`. |
| `relatedModels.lite` | `ecnu-max` | Model used for background tasks (summaries, titles, Explore subagent). Point it to a non-thinking model to avoid wasting reasoning tokens on low-value work. |
| `relatedModels.reasoning` | `ecnu-reasoner` | Model used when WorkBuddy internally needs a reasoning model. |
| `temperature` | omit | ECNU documents that sampling parameters may be ignored under thinking mode. Omitting it lets the server use its default. |
| `useCustomProtocol` | `false` (or omit) | When `true`, WorkBuddy uses the URL as-is without appending `/chat/completions`. Leave `false` for ECNU. |

## How effort reaches the API

WorkBuddy resolves the effort value in this priority order:

1. Session override (UI "Deep Thinking" selector or `/effort <level>` command)
2. Global `reasoningEffort` setting (persisted by `/effort`)
3. Model entry `reasoning.defaultEffort`
4. Model entry `reasoning.effort`
5. Fallback `high` if thinking is enabled and no effort is found

The value is passed through `withSupportedEffortsFallback`, which builds an
identity `thinkingLevelMap` from `supportedEfforts` (each value maps to itself).
Values not in the map are passed through unchanged—this is why `minimal` and
`medium` still reach ECNU and fail.

The `/effort` command accepts all six WorkBuddy tiers
(`minimal`/`low`/`medium`/`high`/`xhigh`/`max`) without filtering by
`supportedEfforts`. Only the UI selector respects the filter. Avoid
`/effort minimal` and `/effort medium`; they bypass the filter and trigger 500.

## Why `thinking` is not in the request

WorkBuddy's `thinking-format-translator` rule is the only code path that
injects `thinking: {"type": "enabled"}` into the request body. It triggers only
when the model is in WorkBuddy's built-in capability catalog (a models.dev
snapshot bundled in `codebuddy.js`, ~1061 entries) and has a `thinkingFormat`
value. `ecnu-max` and `ecnu-reasoner` are not in that catalog, so WorkBuddy
never sends the `thinking` parameter.

This is harmless for ECNU: `ecnu-reasoner` activates thinking server-side
regardless, and `ecnu-max` activates it via `reasoning_effort` alone
([observed](known_deviations.md#ecnu-max-reasoning-effort-as-thinking-trigger)).
The `supportsReasoning` / `supportedEfforts` / `defaultEffort` fields control
which effort value WorkBuddy sends, and the effort value itself is the trigger.

## Verification

After editing `models.json`, WorkBuddy hot-reloads within ~1 second. Check the
daemon log for `Loaded custom models config from user: …models.json` with no
error. The model selector should show both entries with a `custom` tag.

To confirm thinking is active at runtime, inspect the response's
`usage.completion_tokens_details.reasoning_tokens`. Do not rely on
`message.reasoning_content`—it is frequently `null` even when thinking is on
([observed](known_deviations.md#max-thinking-response-fields)).

## ECNU rate-limiting under rapid requests

Sub-second sequential requests to ECNU can return `401` with
`{"detail": "获取第三方元数据失败"}`, mimicking an authentication failure.
Space requests by roughly four seconds to avoid it
([observed](known_deviations.md#rapid-request-401-metadata-failure)). WorkBuddy's
internal request loop serializes calls, so this mainly affects manual debugging
or custom scripts.
