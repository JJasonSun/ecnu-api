# ecnu-api repository guide

This repository is an Agent Skills package for the ECNU LLM Open Platform API.
The repository content is the skill; there is no production application.

## Scope

- `SKILL.md` — concise activation and execution instructions
- `references/api_reference.md` — documented endpoint contracts
- `references/models.md` — models, aliases, credits, quotas, and deployment
- `references/examples.md` — minimal, safe examples
- `references/workflows.md` — implementation, debugging, retry, and test flows
- `references/known_deviations.md` — dated live observations only
- `scripts/smoke_test.py` — opt-in live structural checks
- `scripts/validate_skill.py` — deterministic repository validation
- `tests/` — offline tests for helper behavior

Do not write outside the repository unless the user explicitly asks to install
or synchronize the skill into a client-specific directory.

## Source precedence

When ECNU documentation pages disagree:

1. Use the current model page for model identity, context figures, aliases, and
   capability labels.
2. Use the endpoint page for JSON fields, types, and endpoint-specific limits.
3. Use the quota page for current prices and quota periods.
4. Use release notes to establish when a change occurred.
5. Use `GET /models` for runtime visibility, not as the sole source of
   capability truth.
6. Keep live probes in `known_deviations.md`; never let a single observation
   silently override a documented contract.

## Change workflow

1. Work on a branch.
2. Identify the exact official pages affected by the change.
3. Update only the relevant focused reference.
4. If live testing is needed, use `ECNU_API_KEY` from the environment.
5. Never paste or persist a real key in a file, command example, report, issue,
   commit, or pull request.
6. Run:

```bash
python scripts/validate_skill.py
python -m unittest discover -s tests -v
uvx --from skills-ref agentskills validate .
```

7. Review the diff for secrets, machine-specific paths, duplicated guidance,
   undocumented request fields, and accidental billable calls.
8. Summarize whether each changed claim is documented, observed, or unverified.

## Live verification rules

- The default smoke test performs model-list checks only.
- Chat, embedding, and Anthropic probes require `--low-cost` or `--anthropic`.
- Do not add image generation to an automatic or CI smoke test.
- Do not blindly retry image, TTS, or any other billable request after an
  ambiguous network failure.
- Record SDK or Python version, account type, date, endpoint, status, content
  type, and structural result.
- Sanitize reports before sharing or committing them.
- Update the date in `known_deviations.md` only when the behavior was actually
  reproduced.

## Content conventions

- Write documentation in English; retain official Chinese UI labels where
  needed.
- Prefer imperative, stepwise instructions over broad prose.
- Keep `SKILL.md` below the Agent Skills recommended size and route detail to
  focused references.
- Never describe `skills-ref` validation as an API correctness test.
- Never claim undocumented limits.
- Never describe an output dimension as a request parameter unless ECNU
  documents it.
- Use environment variables in every credential example.

## Current state

The reference content is aligned with the ECNU documentation and repository
observations available on 2026-08-22. The live deviations remain dated
2026-08-21 until a new authenticated run reproduces or supersedes them.
