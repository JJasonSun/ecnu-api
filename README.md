# ECNU API Agent Skill

An unofficial skill that helps an Agent connect to the ECNU / ChatECNU LLM
Open Platform without repeatedly finding the same docs or rediscovering the
same integration differences.

The default path is small: a working connection example, task-specific official
documentation, and a few ECNU-specific recipes. Full live diagnostics are opt-in.
This is not another API manual, a generic Agent course, or a required test harness.

## Install and use

```bash
npx skills add JJasonSun/ecnu-api
```

Example request:

```text
Use $ecnu-api to adapt this application to ECNU. Keep the current framework.
Only change the integration and its relevant checks; do not make live requests.
```

For an existing global installation:

```bash
npx skills update -g ecnu-api
```

Configure `ECNU_API_KEY` through the local environment or secret manager when
execution is needed. Never paste a real key into chat or commit it. Missing
credentials should not prevent the Agent from writing or reviewing code.

## Where to go

| Need | Resource |
|---|---|
| Start a normal integration | [SKILL.md](SKILL.md) |
| Find the relevant official endpoint contract | [Endpoint map](references/api_reference.md) |
| LangChain embeddings, thinking/tool history, Anthropic SDK | [Integration recipes](references/examples.md) |
| Model choice or current account facts | [Model/account pointers](references/models.md) |
| Diagnose a failure or select a live probe | [Targeted diagnosis](references/workflows.md) |
| Inspect dated evidence | [Known deviations](references/known_deviations.md) |
| Maintain this repository | [AGENTS.md](AGENTS.md) |
| Continue this simplification locally | [Implementation and handoff plan](docs/skill-refactor-plan.md) |

The older [Agent-development notes](references/agent_development.md) remain to
preserve historical prompt-fixture references in the observation log. They are
not part of the default integration reading path or a current model benchmark.

## Validation and evidence

The existing runner and unit tests are retained. Maintainer commands are in
`AGENTS.md`; they are not steps for an Agent editing someone else's application.
Live checks require appropriate authorization and a cumulative credit budget.
A documentation edit is not a new live test: observation dates and statuses must
not be refreshed without reproducing the relevant behavior.

Use current official pages for changing contracts, models, prices, and quotas.
Use local recipes to save integration work and dated observations to diagnose
specific discrepancies. Do not assume compatibility with every upstream feature.

## Disclaimer

This community skill is not endorsed by or affiliated with East China Normal
University. Never commit credentials, private prompts, personal data, raw live
responses, generated media, or one-time access URLs.
