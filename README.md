# ECNU API Codex Skill

Unofficial community Codex skill for working with the ECNU / ChatECNU LLM Open
Platform API.

This skill helps Codex answer questions and write integrations for:

- OpenAI-compatible chat completions
- Vision / multimodal chat
- Embeddings and rerank
- Image generation
- Text-to-speech
- Structured output
- Anthropic-compatible API usage
- Models, authentication, quotas, and error handling

## Install

Copy or clone this folder into your Codex skills directory:

Windows PowerShell:

```powershell
Copy-Item -Recurse D:\Workspace\ecnu-api $env:USERPROFILE\.codex\skills\ecnu-api
```

macOS or Linux:

```bash
mkdir -p ~/.codex/skills
cp -R /path/to/ecnu-api ~/.codex/skills/ecnu-api
```

From a Git clone on macOS or Linux:

```bash
git clone <your-repo-url> ~/.codex/skills/ecnu-api
```

Then invoke it with prompts such as:

```text
Use $ecnu-api to help me integrate with the ECNU LLM Open Platform API.
```

## Files

- `SKILL.md`: skill trigger metadata and quick navigation.
- `references/api_reference.md`: endpoint summaries and request/response notes.
- `references/models.md`: models, aliases, credits, quotas, and errors.
- `references/examples.md`: short Python SDK and direct HTTP examples.
- `agents/openai.yaml`: Codex UI metadata.

## Validate

This repository uses `uv` for the validation environment. The validator depends
on `PyYAML`, which is listed in `pyproject.toml`.

Windows PowerShell:

```powershell
$env:PYTHONUTF8 = "1"
uv run --group dev python C:\Users\Jason\.codex\skills\.system\skill-creator\scripts\quick_validate.py D:\Workspace\ecnu-api
```

macOS or Linux:

```bash
PYTHONUTF8=1 uv run --group dev python ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py /path/to/ecnu-api
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
