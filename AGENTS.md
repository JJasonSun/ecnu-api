# ecnu-api repository guide

## Purpose

This repository is an Agent Skills package for the ECNU LLM Open Platform API.
The repository content is the skill; there is no production application.

## File routing

- `SKILL.md` is the concise task entry point.
- `references/api_reference.md` contains documented endpoint contracts.
- Model selection and Agent design: `references/models.md` and `references/agent_development.md`.
- `references/examples.md` contains minimal safe examples.
- `references/workflows.md` contains executable integration and test flows.
- `references/known_deviations.md` contains dated live observations only.
- `scripts/smoke_test.py` performs opt-in live structural checks.
- `scripts/validate_skill.py` and `tests/` provide offline validation.

## Editing rules

- Treat current official ECNU documentation as the documented contract.
- Keep documented facts, live observations, application policy, and unverified
  claims distinct.
- Do not invent undocumented fields, limits, model capabilities, or prices.
- Put point-in-time behavior only in `known_deviations.md` with dated evidence.
- Keep examples sequential, timeout-bounded, and environment-key based.
- Maintain this repository with Git; update the deployed skill via `npx skills update -g ecnu-api`, never by manually copying it.

## Validation

Run before committing:

```bash
python3 scripts/validate_skill.py
python3 -m unittest discover -s tests -v
python3 -m compileall scripts tests
uvx --from skills-ref agentskills validate "$PWD"
```

Review `git diff --check` and scan tracked content for secrets and personal paths.

## Safety

- Read live credentials only from `ECNU_API_KEY`; never accept a CLI key.
- Never commit keys, Authorization values, private inputs, raw responses,
  generated media, one-time URLs, or full reasoning content.
- Keep API calls serial and enforce the declared credit ceiling.
- Do not automatically retry POST requests after ambiguous transport failures.
- Record only sanitized response structure and allowlisted diagnostic headers.
- Do not update an observation date unless the behavior was reproduced.
