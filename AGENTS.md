# ecnu-api skill repo

Agent Skills package for the ECNU LLM Open Platform API. The repo content IS
the skill; there is no runnable application code.

## Deploy

Edit files in this repo, then copy the changed files to
`C:\Users\Jason\.agents\skills\ecnu-api\` to take effect. That directory is a
full mirror of this repo; verify file hashes match after every sync.

## Layout

- `SKILL.md` — skill entry: protocol roots, endpoint map, critical contracts
- `references/api_reference.md` — exact request fields, limits, response shapes
- `references/models.md` — models, aliases, credits, quotas, Recent Changes log
- `references/examples.md` — Python and HTTP examples
- `README.md` — human-facing overview for GitHub

## Conventions

- Official docs at developer.ecnu.edu.cn are the authority. Never invent
  undocumented limits; write "not documented" instead.
- `references/models.md` keeps a `Recent Changes` section; new entries go on
  top, newest first.
- Content is English; keep official Chinese terms (voice names, UI labels)
  as-is.
- Never commit real API keys.

## Current state (2026-08-22)

- Synced with official docs through v3.2.1 (2026-08-10) and the doc
  restructure of 2026-08-09 (security/tos pages published; vision page merged
  into the completions multimodal section).
- Responses-API `reasoning.effort` is documented from release notes; the
  responses.html page itself still lags.
- Live-verified against the service on 2026-08-21; deviations are recorded in
  `references/api_reference.md` under Live Verification Notes.

## Verifying changes

Fetch each page listed in Official Sources, diff against the reference files,
patch stale statements, then sync to the `.agents` mirror and verify hashes.
