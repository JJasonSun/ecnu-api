# Glossary

Terms used across the skill, its maintenance rules and pull requests.

| Term | Meaning |
|---|---|
| **Contract** | What the current official ECNU documentation states. The skill links to it rather than copying it. |
| **Documented** | Supported by a linked official page. Evidence column value: `docs`. |
| **Observed** | Seen on the live service on a stated date, reproducible with a runner case. |
| **Deviation** | An observed behavior that differs from the contract; a row in `references/troubleshooting.md`. |
| **Runner** | `scripts/smoke_test.py`: serial, budgeted, redacting live checks. |
| **Runner case** | One named check in the runner (for example `effort_only_ecnu_plus`); every observed row names one. |
| **Profile** | A group of runner cases: `auth`, `core`, `compatibility`, `billable`, `all`. |
| **Revalidation** | After an ECNU release: reread every linked page, run `--profile all`, delete rows whose case passes, redate the rest. |
| **Snapshot** | The dated model table in `references/models.md`, the only copied official values. |
| **Recipe** | A small ECNU-specific code example in `references/examples.md`, each covered by an offline test. |
| **Routing table** | The single task → official page → local help table in `SKILL.md`. |
| **Audit** | The read-only check of an existing integration in `references/audit.md`. |
| **Primary model** | `ecnu-plus` or `ecnu-max`. Older names such as `ecnu-reasoner` are **aliases**. |
| **Effort tier** | A `reasoning_effort` value; valid tiers differ per primary model. |
| **Credits** | ECNU's billing unit; personal tokens share a rolling 7-day pool. |
| **Peak hours** | The weekday daytime window when token prices double. |
| **Side-effect-free call** | A request safe to resend (embedding, rerank, decision); chat, image and TTS are not. |
