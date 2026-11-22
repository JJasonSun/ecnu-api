# ecnu-api repository guide

This repository is an Agent Skill, not an application. These rules are for
maintaining it, not for projects that consume the skill.

## What belongs in the skill

The official ECNU docs are the contract. Keep only what they do not provide:
task routing, production practice, small recipes, and current live deviations.
Link to official values instead of copying them; the one exception is the dated
model snapshot in `references/models.md`. Do not keep history: Git has it.

## Files

- `SKILL.md`: entry point, connection example, single routing table.
- `references/examples.md`: ECNU-specific recipes; each code block has an offline test.
- `references/engineering.md`: concurrency, retries, timeouts, cost, errors.
- `references/models.md`: dated model snapshot and account pages.
- `references/troubleshooting.md`: symptom table, live deviations, runner usage.
- `scripts/smoke_test.py`: live runner; `scripts/validate_skill.py` and `tests/`: offline checks.

## Rules

- Every observed (non-documented) row names a runner case; add the case first.
- Do not invent limits or copy upstream model defaults into ECNU requests.
- Change an observation date only after rerunning its case.
- After an ECNU release: recheck the docs, run `--profile all`, update the model
  snapshot, delete rows whose case now passes, and redate the rest.
- Update installed copies via `npx skills update -g ecnu-api`, not by copying.

## Validation

Manage Python with `uv`; do not assume `python3` is on PATH (e.g. on Windows).

```bash
uv run --no-project python scripts/validate_skill.py
uv run --no-project --with requests --with httpx --with openai --with anthropic python -m unittest discover -s tests -v
uv run --no-project python -m compileall scripts tests
uvx --from skills-ref agentskills validate "$PWD"
git diff --check
```

Report unavailable checks as not run. Live checks read only `ECNU_API_KEY`, run
serially and never retry an ambiguous POST. Maintainer live tests of this
repository are pre-authorized with no credit ceiling; pass a large explicit
`--max-credits` (the runner requires a finite value). This does not change the
skill's 50-credit default for consuming apps. Keep sanitized reports under the
ignored `.live-artifacts/`; never commit keys, private inputs, reasoning,
generated media, one-time URLs or raw responses.
