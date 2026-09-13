# ecnu-api repository guide

## Purpose

This is an Agent Skills package, not a production application.
Optimize for less repeated setup, lookup, and troubleshooting work.
These instructions apply to maintaining this repository, not consuming apps.

## File routing

- `SKILL.md`: small integration entry point and task routing.
- `references/api_reference.md`: official endpoint links, not copied field tables.
- `references/models.md`: selection defaults and current account-source pointers.
- `references/examples.md`: ECNU-specific integration recipes.
- `references/workbuddy_setup.md`: WorkBuddy desktop custom-model configuration recipe.
- `references/workflows.md`: symptom-driven, opt-in diagnostics.
- `references/known_deviations.md`: dated live evidence; preserve dates and scope.
- `references/agent_development.md`: historical guidance cited by old observations.
- `scripts/` and `tests/`: existing diagnostics and offline validation.
- `docs/skill-refactor-plan.md`: refactor scope and acceptance evidence.

## Editing rules

- Prefer current official contracts; keep observed differences separately dated.
- Add content only when it saves a concrete lookup, decision, mistake, or repeated action.
- Keep everyday integration separate from platform audits and repository maintenance.
- Do not invent API limits or copy upstream model defaults into ECNU requests.
- Do not refresh a test date or label a snippet live-verified without a real test.
- Update installed copies via `npx skills update -g ecnu-api`, not manual copying.

## Validation

```bash
python3 scripts/validate_skill.py
python3 -m unittest discover -s tests -v
python3 -m compileall scripts tests
uvx --from skills-ref agentskills validate "$PWD"
git diff --check
```

Report unavailable checks as not run. Review tracked changes for secrets.
Live checks use only `ECNU_API_KEY`, serial requests, no ambiguous POST retry,
and an approved cumulative budget. Never commit private inputs, reasoning,
credentials, generated media, one-time URLs, or raw responses. Keep sanitized
live artifacts under the ignored `.live-artifacts/` directory.
