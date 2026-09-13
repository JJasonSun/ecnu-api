---
name: ecnu-api
description: >
  Connect an application or SDK to the ECNU / ChatECNU LLM Open Platform
  at chat.ecnu.edu.cn, or diagnose an ECNU API failure. Covers chat,
  Responses, tools, vision, embeddings, rerank, images, TTS, and
  Anthropic-compatible clients. Not for general ECNU information,
  unrelated model questions, or generic Agent/prompt design.
---

# ECNU API integration

Help the user finish the requested integration, not audit the whole platform.
Keep their working framework and chosen model unless the task requires a change.
Use the relevant official contract plus the ECNU-specific notes below.

## Start with a working connection

For a new, ordinary text integration, use `ecnu-plus` as a starting point.
This is an application default, not a claim that it is best for every task.
Read the key from `ECNU_API_KEY`; a missing key does not block writing code.
Install `openai` in the project's existing environment if it is needed.
This example makes one real request: do not run it for a code-only request.

```python
import os
from openai import OpenAI

client = OpenAI(
    api_key=os.environ["ECNU_API_KEY"],
    base_url="https://chat.ecnu.edu.cn/open/api/v1",
    timeout=60.0,
    max_retries=0,
)
response = client.chat.completions.create(
    model="ecnu-plus",
    messages=[{"role": "user", "content": "Reply with a short greeting."}],
    max_tokens=128,
)
if not response.choices or response.choices[0].finish_reason != "stop":
    raise RuntimeError("No complete text response; inspect the result before retrying")
text = response.choices[0].message.content
if not text:
    raise RuntimeError("The response contained no text")
print(text)
```

For an Anthropic client, the base is
`https://chat.ecnu.edu.cn/open/api/anthropic`, not the OpenAI `/v1` base.
Its full messages URL ends in `/open/api/anthropic/v1/messages`.

## Read only what this task needs

| Task | Next resource |
|---|---|
| Chat, streaming, vision, Responses, JSON, rerank, images, TTS, or browser integration | [Official endpoint map](references/api_reference.md): open only the matching page |
| LangChain embeddings | [Embedding recipe](references/examples.md#langchain-embeddings) |
| Anthropic SDK setup | [Anthropic recipe](references/examples.md#anthropic-sdk) |
| Thinking and tool continuation | [Tool-history recipe](references/examples.md#thinking-and-tool-history) plus the linked ECNU contract |
| WorkBuddy desktop custom-model setup | [WorkBuddy recipe](references/workbuddy_setup.md) |
| Model choice, prices, quotas, or deployment questions | [Model and account pointers](references/models.md) |
| An error, unexpected result, or requested live check | [Targeted diagnosis](references/workflows.md); consult only the matching dated deviation |

A basic code edit does not require reading all references or running a smoke
profile. API compatibility is not proof that every upstream field is supported.
Current official pages define documented contracts; local observations are dated
exceptions, not permanent guarantees. If a page is unreachable, use relevant
local material to continue offline work and state what could not be rechecked.
Do not present an old price, quota, or capability as freshly verified.

## Execution boundary

Only make live requests when needed and covered by the user's authorization
for the account, data, destination, purpose, and budget. Reuse authorization
within that scope; ask only about a missing or materially changed part.
Never request a key in chat or put credentials, private prompts, or reasoning
in logs. A missing execution permission blocks that request, not offline work.

For live probes, check current prices, use synthetic input, run serially, and
select the smallest relevant case. The runner's default ceiling is 50 credits,
not permission to spend them; obey any lower approved limit and obtain separate
authorization before exceeding 50. Do not reset the budget per request.
Do not automatically repeat a possibly accepted POST after a timeout or dropped
connection. See the diagnosis reference only when execution is actually needed.

Finish with the requested code or answer and what was actually checked.
Do not impose a provenance-report template on routine work. Repository-maintainer
checks belong in `AGENTS.md`, not in a consuming application's workflow.
