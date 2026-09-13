# Integration recipes

Read only the section matching the current task. These are small integration
patterns, not a replacement SDK or a complete application. For ordinary chat,
use the example in [SKILL.md](../SKILL.md); for other endpoints, go straight to
the [official page](api_reference.md).

The executable examples below make real requests when run. Use the project's
existing environment and dependencies; do not install or run them for a
code-only request. Live execution follows the authorization and budget boundary
in the skill. Checked versions and scope are recorded in the
[dated recipe coverage](known_deviations.md#verified-recipe-coverage-on-2026-09-12);
an example edit alone does not refresh that evidence.

## LangChain embeddings

The [ECNU embedding contract](https://developer.ecnu.edu.cn/vitepress/llm/api/embedding.html)
accepts strings, not OpenAI token-ID arrays. Disable LangChain's token conversion.
The official LangChain example sets `dimensions` to 1024, but the request table
lists only `model` and `input` and does not explain dimension selection.
This recipe omits `dimensions` and validates the documented 1024-value output,
following the dated recipe coverage above. That check does not establish whether
the service accepts or rejects the field. Reject an empty list before making a call.

Standalone example; requires `langchain-openai`:

```python
import os
from langchain_openai import OpenAIEmbeddings

embeddings = OpenAIEmbeddings(
    api_key=os.environ["ECNU_API_KEY"],
    base_url="https://chat.ecnu.edu.cn/open/api/v1",
    model="ecnu-embedding-small",
    check_embedding_ctx_length=False,
    timeout=60.0,
    max_retries=0,
)
texts = ["Hello world", "Example document"]
if not texts or any(not isinstance(text, str) for text in texts):
    raise ValueError("Expected a non-empty list of strings")
vectors = embeddings.embed_documents(texts)
if len(vectors) != len(texts) or any(len(vector) != 1024 for vector in vectors):
    raise RuntimeError("Unexpected embedding count or vector length")
print(f"Received {len(vectors)} vectors")
```

For longer inputs, follow the current endpoint's character limit and split
locally. Do not infer an undocumented batch maximum from per-call billing.
When using direct HTTP, align vectors with inputs by their returned `index`.

## Thinking and tool history

Use the [ECNU thinking contract](https://developer.ecnu.edu.cn/vitepress/llm/thinking.html)
and the wire format of the chosen endpoint. For Chat Completions, enable
thinking through `thinking.type`; direct `reasoning_effort` uses `low`, `high`,
or `max` on `ecnu-max` and is ignored by `ecnu-plus`. Pass ECNU extensions through
`extra_body` with the OpenAI SDK. Do not substitute upstream template switches.

For a tool exchange, append the complete actual assistant message before the
matching tool results. ECNU documents preserving `reasoning_content` for
thinking-mode tool calls through subsequent user turns. Keep it only in process
memory. The [2026-09-12 observation](known_deviations.md#max-thinking-response-fields)
records varying returned fields: preserve what exists, do not fabricate a
missing field, and do not infer thinking was disabled from its absence.

Integration fragment for an existing **direct-HTTP** loop; `assistant_message`
is the original response message, `tool_results` contains already validated,
authorized tool results, and each result has a matching call ID:

```python
from copy import deepcopy

messages.append(deepcopy(assistant_message))
for call_id, result_text in tool_results:
    messages.append({
        "role": "tool",
        "tool_call_id": call_id,
        "content": result_text,
    })
# Send this continuing history, and retain it for the next user turn.
# Do not print or persist reasoning_content, reasoning, or private tool output.
```

For an OpenAI SDK Chat Completions response, first obtain `assistant_message`
for the fragment above:

```python
assistant_message = response.choices[0].message.model_dump(
    mode="json", exclude_unset=True
)
```

This retains returned extension fields without adding absent optional fields.
Only execute complete, validated tool arguments, not partial streamed JSON.
For other SDKs/frameworks, check their serialization; do not blindly convert
Responses or Anthropic blocks into Chat roles. An endpoint smoke pass is not
proof that a framework adapter works.

## Anthropic SDK

Use the [Anthropic-compatible contract](https://developer.ecnu.edu.cn/vitepress/llm/api/anthropic.html),
not the OpenAI root. Standalone example; requires `anthropic`:

```python
import os
from anthropic import Anthropic

client = Anthropic(
    api_key=os.environ["ECNU_API_KEY"],
    base_url="https://chat.ecnu.edu.cn/open/api/anthropic",
    timeout=60.0,
    max_retries=0,
)
message = client.messages.create(
    model="ecnu-plus",
    max_tokens=128,
    messages=[{"role": "user", "content": "Reply with a short greeting."}],
)
text = "".join(block.text for block in message.content if block.type == "text")
if message.stop_reason != "end_turn" or not text:
    raise RuntimeError("No complete text response; inspect the result before retrying")
print(text)
```

Use plain model names unless the caller actually requires the `[1m]` context
signal. Do not automatically treat a suffix-specific `401` as a bad key; follow
[the dated control/fallback conditions](known_deviations.md#anthropic-long-context-suffix-metadata).
Do not silently downgrade context or map unsupported effort values.
