# ECNU API Agent Skill

Unofficial community [Agent Skill](https://agentskills.io/) for implementing,
reviewing, testing, and troubleshooting integrations with the ECNU / ChatECNU
LLM Open Platform API.

The skill covers:

- OpenAI-compatible Chat Completions and Responses APIs
- vision and multimodal messages
- embeddings and rerank
- image generation and text-to-speech
- structured output
- Anthropic-compatible API usage
- model selection, authentication, quotas, errors, and known service deviations

## Install

```bash
npx skills add JJasonSun/ecnu-api
```

Or copy this repository into the skills directory used by an Agent
Skills-compatible client. Keep the installed directory name as `ecnu-api` so it
matches the `name` in `SKILL.md`.

Example invocation:

```text
Use $ecnu-api to review this ECNU API integration.
```

## Repository layout

```text
ecnu-api/
├── SKILL.md
├── AGENTS.md
├── references/
│   ├── api_reference.md
│   ├── models.md
│   ├── examples.md
│   ├── workflows.md
│   └── known_deviations.md
├── scripts/
│   ├── smoke_test.py
│   └── validate_skill.py
├── tests/
│   └── test_smoke_test.py
└── .github/workflows/validate.yml
```

`SKILL.md` contains the core workflow and tells an agent when to load each
focused reference. Live observations are isolated from documented contracts in
`references/known_deviations.md`.

## Configure a key safely

Store the key in an environment variable. Do not put it in source files, shell
scripts, screenshots, committed reports, or chat prompts.

PowerShell:

```powershell
$env:ECNU_API_KEY = "your-api-key"
```

macOS or Linux:

```bash
export ECNU_API_KEY="your-api-key"
```

A key pasted into a chat or public location should be revoked or rotated after
testing.

## Reproducible smoke tests

The default profile performs model-list checks and does not send chat,
embedding, Anthropic, image, or TTS POST requests:

```bash
python scripts/smoke_test.py
```

Low-cost POST probes are explicit:

```bash
python scripts/smoke_test.py --low-cost --anthropic \
  --account-type personal-token \
  --output smoke-results.json
```

The report contains statuses and structural summaries. It does not print the
API key or successful model content. Image generation is intentionally absent
from the automated smoke test because it is comparatively expensive and a
retry after an ambiguous failure could duplicate charges.

## Validate the skill

Run deterministic repository checks and unit tests:

```bash
python scripts/validate_skill.py
python -m unittest discover -s tests -v
```

Run the Agent Skills reference validator separately:

```bash
uvx --from skills-ref agentskills validate .
```

The reference validator checks format and naming conventions; it does not
verify that ECNU endpoints are currently available or that every documented
contract matches live behavior.

## Maintenance principles

- Official ECNU documentation is the authority for documented contracts.
- Runtime observations must include a date and must remain labeled as
  observations.
- Do not infer unsupported OpenAI or Anthropic fields.
- Keep examples minimal and secrets environment-based.
- Do not add local absolute paths or machine-specific deployment instructions.
- Run repository validation before opening a pull request.

## Official documentation

API details can change. Verify production-critical behavior against the current
ECNU developer documentation:

- https://developer.ecnu.edu.cn/vitepress/llm/model.html
- https://developer.ecnu.edu.cn/vitepress/llm/thinking.html
- https://developer.ecnu.edu.cn/vitepress/llm/authorization.html
- https://developer.ecnu.edu.cn/vitepress/llm/limit.html
- https://developer.ecnu.edu.cn/vitepress/llm/error.html
- https://developer.ecnu.edu.cn/vitepress/llm/release.html
- https://developer.ecnu.edu.cn/vitepress/llm/api/models.html
- https://developer.ecnu.edu.cn/vitepress/llm/api/completions.html
- https://developer.ecnu.edu.cn/vitepress/llm/api/responses.html
- https://developer.ecnu.edu.cn/vitepress/llm/api/embedding.html
- https://developer.ecnu.edu.cn/vitepress/llm/api/rerank.html
- https://developer.ecnu.edu.cn/vitepress/llm/api/imagegenerate.html
- https://developer.ecnu.edu.cn/vitepress/llm/api/audio.html
- https://developer.ecnu.edu.cn/vitepress/llm/api/anthropic.html
- https://developer.ecnu.edu.cn/vitepress/llm/api/structuredoutput.html
- https://developer.ecnu.edu.cn/vitepress/llm/tos.html

## Disclaimer

This is an unofficial community skill. It is not endorsed by or affiliated with
East China Normal University. Never commit API keys, personal tokens, internal
allowlist details, private prompts, or unsanitized live-test output.
