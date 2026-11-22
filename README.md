# ECNU API Agent Skill

An unofficial Agent skill for building on the ECNU / ChatECNU LLM Open
Platform: connect an application or SDK, harden it for production, and
diagnose failures without rediscovering the same differences each time.

## Install and use

```bash
npx skills add JJasonSun/ecnu-api
```

Update an existing global installation:

```bash
npx skills update -g ecnu-api
```

Example request:

```text
Use $ecnu-api to adapt this application to ECNU. Keep the current framework.
Only change the integration and its relevant checks; do not make live requests.
```

Configure `ECNU_API_KEY` through the environment or a secret manager when
execution is needed. Never paste a real key into chat or commit it.

## What this adds to the official docs

The [official documentation](https://developer.ecnu.edu.cn/vitepress/llm/model.html)
is the contract and changes often, so the skill links to it instead of copying
it, and keeps only what the docs do not give an Agent:

| Need | Where |
|---|---|
| Which protocol, model and official page fit a task | [SKILL.md](SKILL.md) |
| Small ECNU-specific recipes, each covered by an offline test | [Recipes](references/examples.md) |
| Concurrency, retries, timeouts, cost and error handling in production | [Engineering](references/engineering.md) |
| Read-only audit or migration of an existing integration | [Audit](references/audit.md) |
| Current model snapshot and account pages | [Models](references/models.md) |
| Symptoms, current live deviations, and how to rerun them | [Troubleshooting](references/troubleshooting.md) |

Every live observation names a runner case in `scripts/smoke_test.py`, so it
can be reproduced or retired after an ECNU release. History lives in Git:
observations that no longer reproduce are deleted, not archived. Maintainer
rules are in [AGENTS.md](AGENTS.md).

## Disclaimer

This community skill is not endorsed by or affiliated with East China Normal
University. Never commit credentials, private prompts, personal data, raw live
responses, generated media, or one-time access URLs.
