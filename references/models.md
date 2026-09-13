# Model and account pointers

Keep the user's working model unless they need selection help. For a new
ordinary text task, `ecnu-plus` is the local starting default; consider
`ecnu-max` for more demanding tasks. This is a practical starting point, not
a measured quality or latency ranking.

## Find the current answer

| Question | Source |
|---|---|
| Supported model IDs, aliases, vision, context, underlying models | [Official model page](https://developer.ecnu.edu.cn/vitepress/llm/model.html) |
| Thinking switch and protocol-specific effort | [Thinking](https://developer.ecnu.edu.cn/vitepress/llm/thinking.html), then the chosen [endpoint](api_reference.md) |
| Token prices, fixed request costs, shared allowances, quota windows | [Current quota and pricing page](https://developer.ecnu.edu.cn/vitepress/llm/limit.html) |
| Obtain/configure credentials | [Authorization](https://developer.ecnu.edu.cn/vitepress/llm/authorization.html) |
| Residency, fallback, submitted data, retention, contractual requirements | [Data security](https://developer.ecnu.edu.cn/vitepress/llm/security.html) and [developer agreement](https://developer.ecnu.edu.cn/vitepress/llm/tos.html) |
| What changed and when | [Release notes](https://developer.ecnu.edu.cn/vitepress/llm/release.html) |
| Is there a reported incident? | [Service status](https://chat.ecnu.edu.cn/status) |

## ECNU-specific boundaries

Use primary ECNU model names for new integrations rather than upstream names
or historical aliases. A response's `model` metadata need not echo the requested
name. `/models` is runtime visibility, not a capability or authentication test.

Upstream model cards can explain model design, but do not establish ECNU's
request fields, thinking defaults, context units, output limits, performance,
or deployment path. Do not copy upstream serving flags into requests.

For thinking mode, the alias `ecnu-reasoner` activates thinking server-side
without a client-side `thinking` parameter
([observed](known_deviations.md#ecnu-reasoner-alias-default-thinking)).
On `ecnu-max`, `reasoning_effort` alone triggers thinking, contrary to the
documented gating
([observed](known_deviations.md#ecnu-max-reasoning-effort-as-thinking-trigger)).
Restrict `reasoning_effort` to `low`, `high`, `xhigh`, and `max`; `minimal`
and `medium` are unreliable
([observed](known_deviations.md#unavailable-reasoning-effort-tiers)).

For a cost calculation, fetch current prices and show the input/output and
cache assumptions. Do not assume a cache-hit ratio or treat estimated usage as
verified account debit. A code-only task does not require a cost calculation.

If current documentation is unavailable, do not invent current account values.
Continue independent implementation work with the relevant local recipe,
identify the unverified decision, and defer only what depends on that value.

Historical model/Agent discussion remains in
[agent_development.md](agent_development.md) to preserve references from past
observations. It is not required reading for an ordinary integration and is
not a current model benchmark.
