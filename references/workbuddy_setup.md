# WorkBuddy desktop integration

Connect ECNU to WorkBuddy desktop as a custom OpenAI-compatible model source.
The desktop implementation and startup behavior below were inspected on
2026-09-12; they have not been revalidated on current WorkBuddy builds.
The configuration follows the [ECNU model contract](https://developer.ecnu.edu.cn/vitepress/llm/model.html)
checked on 2026-10-02, but this revised configuration has not been live-tested.

## Configuration file

The inspected implementation reads custom models from `%USERPROFILE%\.workbuddy\models.json` on
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

## Configuration example

Use `ecnu-reasoner` for thinking and `ecnu-max` for ordinary text requests.
Both are currently text-only. The input/output limits below are conservative
client budgets: together they stay below the documented 512K context, without
assuming whether K means 1000 or 1024. They are not backend maximums.

```json
[
  {
    "id": "ecnu-reasoner",
    "name": "ECNU Max (thinking)",
    "vendor": "ECNU",
    "url": "https://chat.ecnu.edu.cn/open/api/v1/chat/completions",
    "apiKey": "sk-REDACTED",
    "maxInputTokens": 440000,
    "maxOutputTokens": 65536,
    "supportsToolCall": true,
    "supportsImages": false,
    "supportsReasoning": true,
    "reasoning": {
      "defaultEffort": "max",
      "supportedEfforts": ["low", "high", "max"],
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
    "maxInputTokens": 440000,
    "maxOutputTokens": 65536,
    "supportsToolCall": true,
    "supportsImages": false,
    "supportsReasoning": false,
    "relatedModels": {
      "lite": "ecnu-max",
      "reasoning": "ecnu-reasoner"
    }
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
| `supportsReasoning` | `true` on reasoner, `false` on max | Enables the effort controls only for the thinking route in this recipe; it is not a statement that max lacks thinking support. |
| `reasoning.defaultEffort` | `max` on reasoner only | The effort sent when no session or global override is set. |
| `reasoning.supportedEfforts` | `["low","high","max"]` | Current documented max/reasoner tiers; the September 12 `xhigh` result is [historical](known_deviations.md#unavailable-reasoning-effort-tiers). |
| `reasoning.canDisableThinking` / `onlyReasoning` | `false` / `true` on reasoner only | Hide the "Off" entry for this default-thinking route. Select the separate max entry for ordinary requests; these UI settings do not establish that the server cannot disable thinking. |
| `relatedModels.lite` | `ecnu-max` | Routes background work to the ordinary text entry. Verify that session/global overrides do not inject thinking or effort. |
| `relatedModels.reasoning` | `ecnu-reasoner` | Model used when WorkBuddy internally needs a reasoning model. |
| `temperature` | omit | ECNU documents that sampling parameters may be ignored under thinking mode. Omitting it lets the server use its default. |
| `useCustomProtocol` | `false` (or omit) | When `true`, WorkBuddy uses the URL as-is without appending `/chat/completions`. Leave `false` for ECNU. |

## How effort reaches the API

The September 12 implementation resolved effort in this priority order:

1. Session override (UI "Deep Thinking" selector or `/effort <level>` command)
2. Global `reasoningEffort` setting (persisted by `/effort`)
3. Model entry `reasoning.defaultEffort`
4. Model entry `reasoning.effort`
5. Fallback `high` if thinking is enabled and no effort is found

The value is passed through `withSupportedEffortsFallback`, which builds an
identity `thinkingLevelMap` from `supportedEfforts` (each value maps to itself).
Values not in the map are passed through unchanged, so the map is not request
validation.

The `/effort` command accepts all six WorkBuddy tiers
(`minimal`/`low`/`medium`/`high`/`xhigh`/`max`) without filtering by
`supportedEfforts`. Only the UI selector respects the filter. For these
max/reasoner entries, use only `low`, `high`, or `max`; other tiers are outside
the current documented contract. Clear session/global overrides when checking
the ordinary max route, and inspect the actual request.

## Why `thinking` is not in the request

In the inspected build, WorkBuddy's `thinking-format-translator` was the code
path that injected `thinking: {"type": "enabled"}`. It triggered only
when the model is in WorkBuddy's built-in capability catalog (a models.dev
snapshot bundled in `codebuddy.js`, ~1061 entries) and has a `thinkingFormat`
value. `ecnu-max` and `ecnu-reasoner` were absent from that catalog, so this
custom-model route did not send the `thinking` parameter.

This recipe uses the documented default-thinking alias `ecnu-reasoner` for
that route. Current ECNU guidance requires `thinking` to enable thinking on
`ecnu-max`; do not rely on the [September 12 effort-only observation](known_deviations.md#ecnu-max-reasoning-effort-as-thinking-trigger).
If a newer WorkBuddy build adds custom thinking controls, recheck its outgoing
request before changing this routing.

## Verification

The inspected build hot-reloaded `models.json` within ~1 second. Check the
daemon log for `Loaded custom models config from user: …models.json` with no
error. The model selector should show both entries with a `custom` tag.

To confirm thinking is active at runtime, inspect the response's
`usage.completion_tokens_details.reasoning_tokens`. Do not rely on
`message.reasoning_content` alone—it was sometimes `null` with thinking active
in the [September 12 observations](known_deviations.md#max-thinking-response-fields).

## Historical rapid-request errors

On September 12, sub-second sequential requests returned `401` with
`{"detail": "获取第三方元数据失败"}`, while requests spaced roughly four seconds
apart succeeded ([observation](known_deviations.md#rapid-request-401-metadata-failure)).
This association does not establish a rate limit or prove the credential is
valid. After an explicitly rejected request, a spaced control request may help
diagnose it. Keep requests serial; do not automatically retry a possibly
accepted POST after a timeout or dropped connection.
