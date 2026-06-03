# ECNU Models, Quotas, and Errors

## Table of Contents

- [Dialog Models](#dialog-models)
- [Compatibility Aliases](#compatibility-aliases)
- [Embedding and Rerank Models](#embedding-and-rerank-models)
- [Image and TTS Models](#image-and-tts-models)
- [Thinking Mode](#thinking-mode)
- [Quota Limits](#quota-limits)
- [Credits Calculation](#credits-calculation)
- [Error Codes](#error-codes)
- [Official Sources](#official-sources)

---

## Dialog Models

| Model | Base Model | Context | Thinking | Tools | Vision | Positioning |
|---|---|---|---|---|---|---|
| `ecnu-max` | DeepSeek-V4-Flash | 1M | Supported, default off | Yes | No | Flagship model for complex tasks |
| `ecnu-plus` | Qwen3.6-27B | 256K | Supported, default off | Yes | Yes | General-purpose model balancing quality, cost, and speed |

- Use `ecnu-max` for high-quality complex text and code tasks.
- Use `ecnu-plus` for general tasks and all image-understanding workflows.
- ECNU states that listed models are locally deployed on campus servers by
  default. In special cases such as upgrades, failures, or heavy load, cloud
  fallback may be used temporarily to maintain continuity.

## Compatibility Aliases

Prefer `ecnu-max` or `ecnu-plus` for new integrations.

| Historical Name | Equivalent To | Note |
|---|---|---|
| `ecnu-reasoner` | `ecnu-max` + `thinking: {"type": "enabled"}` | Thinking on by default |
| `ecnu-reasoner-lite` | `ecnu-plus` + `thinking: {"type": "enabled"}` | Thinking on by default |
| `ecnu-turbo` | `ecnu-plus` | Legacy alias |
| `ecnu-vl` | `ecnu-plus` | Legacy alias; use for older multimodal samples |
| `InnoSpark` | `ecnu-plus` | Legacy alias |
| `educhat-r1` | `ecnu-plus` | Legacy alias |
| `educhat-general` | `ecnu-plus` | Legacy alias |
| `educhat-psychology` | `ecnu-plus` | Legacy alias |
| `ChatECNU` | `ecnu-plus` | Legacy alias |
| `gpt-4` | `ecnu-plus` | Compatibility alias |

## Embedding and Rerank Models

| Model | Base Model | Capability | Context/Dim |
|---|---|---|---|
| `ecnu-embedding-small` | bge-m3 | Text embeddings | 8K context, 1024-dimensional vectors |
| `ecnu-rerank` | bge-reranker-v2-m3 | Text reranking | 8K context |

## Image and TTS Models

| Model | Base Model | Capability | Notes |
|---|---|---|---|
| `ecnu-image` | Z-Image-Turbo | Text-to-image | Prompt max 1024 chars; prompts over 500 chars may be compressed |
| `ecnu-tts` | CosyVoice2-0.5B | Text-to-speech | Input max 4096 chars |

### TTS Voice Types

| Voice ID | Description |
|---|---|
| `xiayu` | Default voice |
| `liwa` | Alternative voice |

### TTS Audio Formats

`mp3` (default), `opus`, `aac`, `flac`, `wav`, `pcm`

## Thinking Mode

All dialog models support thinking mode through the `thinking` parameter.

Enable thinking:

```json
{
  "model": "ecnu-max",
  "messages": [{"role": "user", "content": "Analyze this problem."}],
  "thinking": {"type": "enabled"}
}
```

Disable thinking explicitly:

```json
{
  "model": "ecnu-reasoner",
  "messages": [{"role": "user", "content": "Answer briefly."}],
  "thinking": {"type": "disabled"}
}
```

When thinking is enabled, responses may include `reasoning_content`.

## Quota Limits

All API requests are metered and limited through unified credits. The new quota
algorithm took effect on **2026-06-01**.

| Period | Default quota |
|---|---|
| Every 5 hours | 2000 credits |
| Daily | 5000 credits |
| Monthly | 50000 credits |

Minute-level rate limiting has been removed, but short-term abnormal
high-frequency traffic may still trigger service protection. Production systems
serving ECNU users may have independent quota pools; contact ECNU for higher
requirements.

## Credits Calculation

### Dialog Models

| Model | Input price | Output/thinking price | Formula |
|---|---|---|---|
| `ecnu-plus` | 100 credits / 1M tokens | 400 credits / 1M tokens | `input_tokens / 1_000_000 * 100 + output_tokens / 1_000_000 * 400` |
| `ecnu-max` | 300 credits / 1M tokens | 1200 credits / 1M tokens | `input_tokens / 1_000_000 * 300 + output_tokens / 1_000_000 * 1200` |

### Flat-Rate Capabilities

| Capability | Model | Credits |
|---|---|---|
| Embedding | `ecnu-embedding-small` | 0.05 credits / call |
| Rerank | `ecnu-rerank` | 0.1 credits / call |
| Image generation | `ecnu-image` | 30 credits / successful generation |
| Text-to-speech | `ecnu-tts` | 5 credits / call |

### Token-to-Credits Estimates

| Quota | `ecnu-plus` input only | `ecnu-plus` 4:1 mix | `ecnu-max` input only | `ecnu-max` 4:1 mix |
|---|---|---|---|---|
| 2000 credits / 5h | ~20M input tokens | ~12.5M total tokens | ~6.67M input tokens | ~4.17M total tokens |
| 5000 credits / day | ~50M input tokens | ~31.25M total tokens | ~16.67M input tokens | ~10.42M total tokens |
| 50000 credits / month | ~500M input tokens | ~312.5M total tokens | ~166.7M input tokens | ~104M total tokens |

For input-heavy work such as document processing, codebase analysis, and RAG,
coverage is usually closer to the input-only estimate.

## Error Codes

| Status | Meaning | Typical cause |
|---|---|---|
| 401 | Unauthorized | Missing token or invalid token |
| 403 | Forbidden | Client IP is not in the third-party whitelist |
| 422 | Unprocessable Entity | Invalid request body |
| 429 | Too Many Requests | Rate limit, service protection, or quota exceeded |

Common response shapes:

```json
{"detail": "缺少 access_token"}
```

```json
{"detail": "无效的令牌"}
```

```json
{"detail": "IP 203.0.113.10 不在白名单中"}
```

```json
{"detail": "请求过于频繁，超过应用的配额限制"}
```

Validation errors may use an array:

```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "model"],
      "msg": "Field required"
    }
  ]
}
```

## Official Sources

- Models: https://developer.ecnu.edu.cn/vitepress/llm/model.html
- Quotas: https://developer.ecnu.edu.cn/vitepress/llm/limit.html
- Errors: https://developer.ecnu.edu.cn/vitepress/llm/error.html
