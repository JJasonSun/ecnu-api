# ECNU API Agent Skill

Unofficial community [Agent Skill](https://agentskills.io/) for working with the
ECNU / ChatECNU LLM Open Platform API.

This skill helps compatible AI agents answer questions and write integrations
for:

- OpenAI-compatible chat completions
- OpenAI-compatible Responses API
- Vision / multimodal chat
- Embeddings and rerank
- Image generation
- Text-to-speech
- Structured output
- Anthropic-compatible API usage
- Models, authentication, quotas, and error handling

## Install

Install with the open Skills CLI:

```bash
npx skills add JJasonSun/ecnu-api
```

See the skill on [skills.sh](https://skills.sh/jjasonsun/ecnu-api/ecnu-api).

Alternatively, clone or copy this repository into the skills directory used by
your Agent Skills-compatible client. Keep the installed directory name as
`ecnu-api`, because the Agent Skills specification requires it to match the
`name` in `SKILL.md`.

The exact skills directory depends on the client. For example:

```text
<client-skills-directory>/ecnu-api/SKILL.md
```

Once installed, ask the agent to work with the ECNU API. Clients that support
explicit skill invocation may also accept prompts such as:

```text
Use $ecnu-api to help me integrate with the ECNU LLM Open Platform API.
```

## Files

- `SKILL.md`: skill trigger metadata and quick navigation.
- `references/api_reference.md`: endpoint summaries and request/response notes.
- `references/models.md`: models, aliases, credits, quotas, and errors.
- `references/examples.md`: short Python SDK and direct HTTP examples.

## Validate

Run the official
[`skills-ref`](https://github.com/agentskills/agentskills/tree/main/skills-ref)
reference validator with `uv`:

```bash
uvx --from skills-ref agentskills validate /path/to/ecnu-api
```

On Windows PowerShell, force UTF-8 when the system locale is not UTF-8:

```powershell
$env:PYTHONUTF8 = "1"
uvx --from skills-ref agentskills validate C:\path\to\ecnu-api
```

## Official Documentation

API details can change. Treat this skill as a working summary and verify
production-critical details against the official ECNU developer docs:

- https://developer.ecnu.edu.cn/vitepress/llm/model.html
- https://developer.ecnu.edu.cn/vitepress/llm/authorization.html
- https://developer.ecnu.edu.cn/vitepress/llm/limit.html
- https://developer.ecnu.edu.cn/vitepress/llm/error.html
- https://developer.ecnu.edu.cn/vitepress/llm/api/models.html
- https://developer.ecnu.edu.cn/vitepress/llm/api/completions.html
- https://developer.ecnu.edu.cn/vitepress/llm/api/responses.html
- https://developer.ecnu.edu.cn/vitepress/llm/api/vision.html
- https://developer.ecnu.edu.cn/vitepress/llm/api/imagegenerate.html
- https://developer.ecnu.edu.cn/vitepress/llm/api/embedding.html
- https://developer.ecnu.edu.cn/vitepress/llm/api/rerank.html
- https://developer.ecnu.edu.cn/vitepress/llm/api/audio.html
- https://developer.ecnu.edu.cn/vitepress/llm/api/anthropic.html
- https://developer.ecnu.edu.cn/vitepress/llm/api/structuredoutput.html
- https://developer.ecnu.edu.cn/vitepress/llm/api/embediframe.html

## Disclaimer

This is an unofficial community skill. It is not endorsed by or affiliated with
East China Normal University. Do not commit API keys, personal tokens, internal
whitelist details, or screenshots containing credentials.
