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

For `ecnu-embedding-small`, the [ECNU embedding contract](https://developer.ecnu.edu.cn/vitepress/llm/api/embedding.html)
accepts strings, not OpenAI token-ID arrays. Disable LangChain's token conversion.
The current parameter table limits `dimensions` to `ecnu-embedding-vl`, although
the page's older LangChain example still sets it for the small model. This recipe
follows the parameter table: omit `dimensions` and validate the small model's
1024-value output. Reject an empty list before making a call. Multimodal inputs
use the [VL recipe](#multimodal-retrieval), not this text-only adapter.

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

## Multimodal retrieval

Use the current [embedding](https://developer.ecnu.edu.cn/vitepress/llm/api/embedding.html)
and [rerank](https://developer.ecnu.edu.cn/vitepress/llm/api/rerank.html) contracts.
Both VL models accept strings or objects with `text`, `image`, or both. An
`image` is a complete PNG/JPEG base64 data URL, not a remote URL or Chat
Completions `image_url` content block. Validate image type, decoded size
(at most 5 MiB) and pixel count (at most 16 million) before encoding/uploading.
Each object holds one image; video and multi-image objects are unsupported.

Request-building fragment for an existing HTTP client; `image_data_url` has
already passed those checks. These dictionaries do not send requests:

```python
item = {"text": "A red flower beside a green leaf", "image": image_data_url}
embedding_payload = {
    "model": "ecnu-embedding-vl",
    "input": [item, "A red flower"],
    "dimensions": 1024,
    "encoding_format": "float",
}
rerank_payload = {
    "model": "ecnu-rerank-vl",
    "query": "A red flower",
    "documents": [item, "A blue car"],
    "top_n": 2,
    "return_documents": False,
}
```

Send `embedding_payload` as JSON to `POST /embeddings`, or `rerank_payload`
as JSON to `POST /rerank`, using the OpenAI-compatible base and Bearer auth.
Keep requests serial when checking both. For embedding, cap batches at 32
items; supported dimensions are 1024/2048/4096, with 4096 as the default.
Check the returned count, unique `index` values and finite vector lengths
against the inputs and requested dimension. `encoding_format=base64` instead
returns little-endian float32 bytes encoded as a string; `usage` may be null.

For rerank, map `results[].index` back to the original candidates and validate
finite scores in [0, 1]. `return_documents=True` can echo entire image data
URLs, so omit that output from logs. The embedding batch limit is not a
documented rerank limit. Both endpoint pages retain an 8192-character text
limit; the model page's 32K context is not permission to exceed it.

Choose the model explicitly. Keep an existing text index on
`ecnu-embedding-small` until a deliberate migration: even a 1024-dimensional
VL vector belongs to a different space. A VL reranker only changes ordering
of candidates; it does not require a new vector index or replace image-text
consistency/education review.

## Image generation and editing

The [model page](https://developer.ecnu.edu.cn/vitepress/llm/model.html) lists
`ecnu-image` as qwen-image-2.1 following the 2026-09-30 upgrade. Use the stable
alias and choose the endpoint according to the task:

- [Generation](https://developer.ecnu.edu.cn/vitepress/llm/api/imagegenerate.html)
  uses JSON at `POST /images/generations`. Prompts are automatically expanded;
  retain the original prompt separately from a returned `revised_prompt`.
  Check this endpoint's allowed `size` values; do not assume arbitrary sizes or
  a batch `n` parameter from OpenAI compatibility.
- [Editing](https://developer.ecnu.edu.cn/vitepress/llm/api/imageedit.html)
  uses multipart at `POST /images/edits`, with one `image` file and a `prompt`
  of at most 1024 characters. Instructions pass through unchanged after safety
  review. Only `n=1` is supported; `size` is ignored and not forwarded.

Both support `url` and `b64_json` results. URLs expire after 24 hours; transfer
them promptly when using URL output. Both add an AI watermark. A successful
HTTP status or non-empty `data` alone is insufficient: a rejected request can
have `err_message` and only a masked `revised_prompt`, without an image.
Do not infer mask, multiple references, transparency, fixed edit dimensions,
or guaranteed character consistency from the editing capability. The editing
page does not specify upload size/format limits; do not copy the VL limits.

Direct HTTP editing fragment; `image_path` names a local image approved for
upload and `prompt` is the editing instruction. Requires `requests`; no SDK
change is needed. This makes one request with no automatic retry:

```python
import base64
import os
import requests

if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 1024:
    raise ValueError("Expected a non-empty editing instruction of at most 1024 characters")
with open(image_path, "rb") as source:
    response = requests.post(
        "https://chat.ecnu.edu.cn/open/api/v1/images/edits",
        headers={"Authorization": f"Bearer {os.environ['ECNU_API_KEY']}"},
        data={"model": "ecnu-image", "prompt": prompt, "response_format": "b64_json"},
        files={"image": source},
        timeout=120,
    )
response.raise_for_status()
body = response.json()
if not isinstance(body, dict) or body.get("err_message"):
    raise RuntimeError("Image edit failed; no output accepted")
items = body.get("data")
if not isinstance(items, list) or len(items) != 1 or not isinstance(items[0], dict):
    raise RuntimeError("Expected one edited image")
encoded = items[0].get("b64_json")
if not isinstance(encoded, str) or not encoded:
    raise RuntimeError("Image edit returned no image bytes")
edited_bytes = base64.b64decode(encoded, validate=True)
if not edited_bytes:
    raise RuntimeError("Image edit returned empty image bytes")
```

Decode with the application's image loader before accepting or saving these
bytes, then save to a new asset path and inspect the result before replacing
the source. The fragment leaves the input file untouched. Actual edit quality,
character retention and output dimensions still require live verification.

## Thinking and tool history

Use the [ECNU thinking contract](https://developer.ecnu.edu.cn/vitepress/llm/thinking.html)
and the wire format of the chosen endpoint. For Chat Completions, enable
thinking through `thinking.type`; direct `reasoning_effort` uses `low` / `high` /
`max` on `ecnu-max`, and `low` / `medium` / `xhigh` on `ecnu-plus`. Effort applies
when thinking is enabled; thinking defaults to off. Pass ECNU extensions through
`extra_body` with the OpenAI SDK. Do not substitute upstream template switches
or silently map an unsupported tier between models.

For clients that cannot send `thinking`, the documented compatibility alias
`ecnu-reasoner` defaults to enabled thinking on `ecnu-max`; see the
[WorkBuddy recipe](workbuddy_setup.md) for one client-specific setup.

The 2026-09-12 observations of [effort-only activation](known_deviations.md#ecnu-max-reasoning-effort-as-thinking-trigger)
and [extra max effort tiers](known_deviations.md#unavailable-reasoning-effort-tiers)
remain historical evidence. They do not override the current contract above or
justify rejecting `medium` on `ecnu-plus`.

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
