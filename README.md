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
- URL-parameter ChatECNU links
- model selection, authentication, quotas, errors, and known service deviations
- upstream Qwen3.8, DeepSeek, and DSpark context, distinct from ECNU guarantees
- Agent prompt templates, tool continuation, context management, and evaluation

## Install

```bash
npx skills add JJasonSun/ecnu-api
```

Use the skills CLI to manage installed copies. For an existing global
installation, update from its upstream source with:

```bash
npx skills update -g ecnu-api
```

Maintain this source repository with Git; do not deploy edits by manually
copying files into an installed skill directory.

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
│   ├── agent_development.md
│   ├── examples.md
│   ├── workflows.md
│   └── known_deviations.md
├── scripts/
│   ├── smoke_test.py
│   └── validate_skill.py
├── tests/
│   ├── test_repository_contracts.py
│   └── test_smoke_test.py
└── .github/workflows/validate.yml
```

`SKILL.md` contains the core workflow and tells an agent when to load each
focused reference. Live observations are isolated from documented contracts in
`references/known_deviations.md`.

For Agent development, start with
[model-specific prompt and tool guidance](references/agent_development.md).
It covers ECNU's differences from upstream DeepSeek-V4.1 and Qwen3.8,
reusable task prompts, thinking/tool history, and checks for actual task success.

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

## Reproducible live validation

The runner reads only `ECNU_API_KEY`, sends requests serially, and does not
retry POST requests. Select the smallest profile that answers the question:

| Profile | Scope |
|---|---|
| `auth` | Service status plus valid, invalid, and missing-token model discovery; no billable POST requests. This is the default. |
| `core` | Low-cost Chat Completions, Responses, embeddings, rerank, vision, structured output, error-shape, OpenAI SDK, and LangChain probes. |
| `compatibility` | Responses vision and Anthropic-compatible models, aliases, effort controls, long-context suffix behavior, vision, and SDK probes. |
| `billable` | Fixed-price TTS and one documented image-generation probe, subject to the credit ceiling. |
| `all` | The union of all four profiles; later billable cases are skipped when the ceiling is reached. |

Examples:

```bash
python3 scripts/smoke_test.py --profile auth --max-credits 0 --output .live-artifacts/auth.json
python3 scripts/smoke_test.py --profile core --max-credits 50 --output .live-artifacts/core.json
python3 scripts/smoke_test.py --profile compatibility --max-credits 50 --output .live-artifacts/compatibility.json
python3 scripts/smoke_test.py --profile billable --max-credits 50 --output .live-artifacts/billable.json
python3 scripts/smoke_test.py --profile all --max-credits 50 --output .live-artifacts/all.json
```

`--max-credits` is a conservative planned-cost gate, defaulting to 50. The
runner reserves each case's estimate before sending it and skips a case that
would exceed the ceiling. The estimate is not proof of the service's actual
debit. Recheck the official quota and pricing page before a live run.

Use `--case` to rerun only named cases within the selected profile; repeat the
flag to select more than one:

```bash
python3 scripts/smoke_test.py --profile core --case openai_sdk_chat \
  --max-credits 1 --output .live-artifacts/openai-sdk-chat.json
```

Keep reports under `.live-artifacts/`, which is Git-ignored. Reports contain
statuses and structural summaries, not the API key, generated content,
reasoning text, media, or one-time URLs.

Selected SDK probes on 2026-08-23 passed with OpenAI Python SDK 2.48.0,
Anthropic Python SDK 0.125.0, `langchain-openai` 0.3.35, and `httpx` 0.28.1.
This is dated, point-in-time evidence, not a blanket compatibility guarantee;
see `references/known_deviations.md` for the observed scope and divergences.

## Validate the skill

Run deterministic repository checks and unit tests:

```bash
python3 scripts/validate_skill.py
python3 -m unittest discover -s tests -v
```

Run the Agent Skills reference validator separately:

```bash
uvx --from skills-ref agentskills validate "$PWD"
```

The reference validator checks format and naming conventions; it does not
verify that ECNU endpoints are currently available or that every documented
contract matches live behavior.

## Maintenance principles

- Official ECNU documentation is the authority for documented contracts.
- Upstream model cards and papers provide background, not ECNU API guarantees.
- Runtime observations must include a date and must remain labeled as
  observations.
- Do not infer unsupported OpenAI or Anthropic fields.
- Keep examples minimal and secrets environment-based.
- Do not add local absolute paths or machine-specific deployment instructions.
- Run repository validation before opening a pull request.

## Revalidate after ECNU platform updates

An ECNU release, model rollout, endpoint change, quota change, or announced fix
is a reason to consider a new targeted validation; it is not evidence that an
active deviation has been resolved. Review the updated official contract,
recalculate the credit allowance, and run only the affected `--case` probes
serially with fresh sanitized evidence. Billable TTS or image probes require
new account-owner authorization and must never run automatically.

Update an observation date or mark a deviation `resolved` only after the same
behavior has been exercised again with the current runner. Preserve the prior
entry when the new run is inconclusive, and record both the changed contract
and the new observed result when the platform update changes expectations.

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
- https://developer.ecnu.edu.cn/vitepress/llm/api/urlchat.html
- https://developer.ecnu.edu.cn/vitepress/llm/tos.html

## Disclaimer

This is an unofficial community skill. It is not endorsed by or affiliated with
East China Normal University. Never commit API keys, personal tokens, internal
allowlist details, private prompts, or unsanitized live-test output.
