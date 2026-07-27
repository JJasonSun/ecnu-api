# ECNU API Examples

These examples favor explicit request shapes and safe defaults. They do not
demonstrate undocumented parameters or parallel calls.

## Table of Contents

- [Setup](#setup)
- [Chat Completions](#chat-completions)
- [Responses API](#responses-api)
- [Thinking and Streaming](#thinking-and-streaming)
- [Tool Calling](#tool-calling)
- [Vision](#vision)
- [Embeddings](#embeddings)
- [LangChain Embeddings](#langchain-embeddings)
- [Rerank](#rerank)
- [Image Generation](#image-generation)
- [Text-to-Speech](#text-to-speech)
- [Structured Output](#structured-output)
- [Anthropic Compatibility](#anthropic-compatibility)
- [Model Discovery](#model-discovery)
- [HTTP Error Handling](#http-error-handling)
- [Sequential Workloads](#sequential-workloads)

## Setup

Install only the SDKs used by the selected examples:

```bash
pip install openai requests
```

Keep the API key in an environment variable.

PowerShell:

```powershell
$env:ECNU_API_KEY = "your-api-key"
```

macOS or Linux:

```bash
export ECNU_API_KEY="your-api-key"
```

Create the OpenAI-compatible client:

```python
import os
from openai import OpenAI

api_key = os.environ["ECNU_API_KEY"]

client = OpenAI(
    api_key=api_key,
    base_url="https://chat.ecnu.edu.cn/open/api/v1",
)
```

## Chat Completions

```python
completion = client.chat.completions.create(
    model="ecnu-plus",
    messages=[
        {"role": "system", "content": "Answer accurately and concisely."},
        {"role": "user", "content": "用一句话介绍华东师范大学。"},
    ],
)

print(completion.choices[0].message.content)
```

The documented roles are `system`, `user`, and `assistant`. Keep
`temperature` and `top_p` between 0 and 1 when setting them explicitly.

## Responses API

Both primary dialog models support the OpenAI Responses format:

```python
response = client.responses.create(
    model="ecnu-max",
    input="用一句话介绍华东师范大学。",
)

print(response.output_text)
```

The ECNU page does not publish a complete list of supported OpenAI Responses
tools or event types. Start with text input and verify advanced features before
depending on them.

## Thinking and Streaming

`thinking` is an ECNU request extension. Pass it through `extra_body`:

```python
completion = client.chat.completions.create(
    model="ecnu-max",
    messages=[{"role": "user", "content": "Analyze this problem."}],
    extra_body={"thinking": {"type": "enabled"}},
)

message = completion.choices[0].message
reasoning = getattr(message, "reasoning_content", None)
if reasoning:
    print("Reasoning:", reasoning)
print("Answer:", message.content)
```

Stream text deltas:

```python
stream = client.chat.completions.create(
    model="ecnu-plus",
    messages=[{"role": "user", "content": "Tell me a short story."}],
    stream=True,
)

for chunk in stream:
    delta = chunk.choices[0].delta.content
    if delta:
        print(delta, end="", flush=True)
```

## Tool Calling

```python
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_current_weather",
            "description": "Get current weather for a city.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "City name, such as Shanghai.",
                    }
                },
                "required": ["location"],
            },
        },
    }
]

completion = client.chat.completions.create(
    model="ecnu-plus",
    messages=[{"role": "user", "content": "What's the weather in Shanghai?"}],
    tools=tools,
)

message = completion.choices[0].message
for call in message.tool_calls or []:
    print(call.id, call.function.name, call.function.arguments)
```

The caller must execute the function and send the result back in a subsequent
message. ECNU does not execute user-defined functions for the caller.

## Vision

Use `ecnu-plus` for new integrations. A public image URL:

```python
completion = client.chat.completions.create(
    model="ecnu-plus",
    messages=[
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Describe this image."},
                {
                    "type": "image_url",
                    "image_url": {"url": "https://example.com/image.jpg"},
                },
            ],
        }
    ],
)

print(completion.choices[0].message.content)
```

A local image as a base64 data URL:

```python
import base64
from pathlib import Path

image_bytes = Path("image.jpg").read_bytes()
image_b64 = base64.b64encode(image_bytes).decode("ascii")

completion = client.chat.completions.create(
    model="ecnu-plus",
    messages=[
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Describe this image."},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{image_b64}"
                    },
                },
            ],
        }
    ],
)
```

The API docs publish no image-count, byte-size, or pixel limit. Do not encode a
web UI upload limit as an API validation rule.

## Embeddings

The key distinction is JSON type:

- One text: `input="..."`
- Multiple texts in one HTTP request: `input=["...", "..."]`
- Unsupported: integer token IDs such as `input=[123, 456]`

### One text

```python
response = client.embeddings.create(
    model="ecnu-embedding-small",
    input="华东师范大学",
)

vector = response.data[0].embedding
assert len(vector) == 1024
print(response.data[0].index, len(vector))
```

### String array

```python
texts = [
    "华东师范大学是综合性研究型大学。",
    "量子计算是计算科学的前沿领域。",
    "求实创造，为人师表。",
]

if not texts or not all(isinstance(text, str) for text in texts):
    raise TypeError("Embedding input must be a non-empty string array")

response = client.embeddings.create(
    model="ecnu-embedding-small",
    input=texts,
)

vectors_by_index = {
    item.index: item.embedding
    for item in response.data
}

for index, text in enumerate(texts):
    vector = vectors_by_index[index]
    assert len(vector) == 1024
    print(index, text[:20], len(vector))
```

The published limit is 8192 characters, but the official page does not say
whether an array is checked per element, by combined characters, or both. It
also publishes no maximum item count. Keep batches conservative and split a
batch on `422` rather than claiming a guessed maximum.

For many texts, call sequential batches:

```python
def chunks(items, size):
    for start in range(0, len(items), size):
        yield items[start:start + size]


all_vectors = []
for batch in chunks(texts, size=16):  # Client policy, not an ECNU limit.
    response = client.embeddings.create(
        model="ecnu-embedding-small",
        input=batch,
    )
    ordered = sorted(response.data, key=lambda item: item.index)
    all_vectors.extend(item.embedding for item in ordered)
```

Do not run these batches concurrently. The size `16` is an application choice
for conservative requests, not a documented platform maximum.

## LangChain Embeddings

```bash
pip install langchain-openai
```

```python
from langchain_openai import OpenAIEmbeddings

embeddings = OpenAIEmbeddings(
    base_url="https://chat.ecnu.edu.cn/open/api/v1",
    api_key=api_key,
    model="ecnu-embedding-small",
    dimensions=1024,
    check_embedding_ctx_length=False,
)

vector = embeddings.embed_query("Hello world")
assert len(vector) == 1024
```

`check_embedding_ctx_length=False` is required because LangChain otherwise may
convert strings into OpenAI token IDs. ECNU accepts strings, not OpenAI token
arrays. `dimensions=1024` describes the fixed output size; it does not request
an alternative size from ECNU.

## Rerank

Use direct HTTP because the OpenAI SDK has no rerank resource:

```python
import requests

documents = [
    "华东师范大学是教育部直属的综合性研究型大学。",
    "量子计算是计算科学的前沿领域。",
    "学校校训是求实创造，为人师表。",
]
top_n = 3

if not documents or not all(isinstance(doc, str) for doc in documents):
    raise TypeError("documents must be a non-empty string array")
if any(len(doc) > 8192 for doc in documents):
    raise ValueError("Each rerank document must be at most 8192 characters")
if not 1 <= top_n <= len(documents):
    raise ValueError("Application policy requires 1 <= top_n <= document count")

response = requests.post(
    "https://chat.ecnu.edu.cn/open/api/v1/rerank",
    headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    },
    json={
        "model": "ecnu-rerank",
        "query": "介绍华东师范大学",
        "documents": documents,
        "return_documents": True,
        "top_n": top_n,
    },
    timeout=60,
)

response.raise_for_status()
for result in response.json()["results"]:
    print(result["index"], result["relevance_score"])
    print(result.get("document", ""))
```

The `top_n <= document count` check is sensible client logic, not a published
ECNU maximum. The service docs specify only the default `top_n=5`.

## Image Generation

```python
response = client.images.generate(
    model="ecnu-image",
    prompt="水墨风，竹林，渔船，湖泊，带斗笠的老翁",
    size="1024x1024",
    response_format="url",
)

print(response.data[0].url)
```

Prompts are limited to 1024 characters and may be compressed over 500
characters. URL results expire after 24 hours; download or transfer them
immediately.

Supported sizes are `512x512`, `768x768`, `720x1280`, `1280x720`, and
`1024x1024`.

## Text-to-Speech

```python
response = client.audio.speech.create(
    model="ecnu-tts",
    input="你好，欢迎使用文本转语音服务。",
    voice="xiayu",
    response_format="mp3",
    speed=1.0,
)

response.stream_to_file("output.mp3")
```

Input is limited to 4096 characters. Voice is `xiayu` or `liwa`; speed is 0.25
through 4.0. Multiple texts require separate sequential API calls:

```python
jobs = [
    ("第一段文本。", "xiayu"),
    ("第二段文本。", "liwa"),
]

for index, (text, voice) in enumerate(jobs, start=1):
    response = client.audio.speech.create(
        model="ecnu-tts",
        input=text,
        voice=voice,
        response_format="mp3",
    )
    response.stream_to_file(f"speech-{index}.mp3")
```

This loop is not a batch request; each iteration consumes one TTS call.

## Structured Output

```python
import json

schema = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "department": {"type": "string"},
        "title": {"type": "string"},
    },
    "required": ["name", "department", "title"],
}

completion = client.chat.completions.create(
    model="ecnu-plus",
    messages=[
        {
            "role": "system",
            "content": (
                "Extract name, department, and title. "
                "Return values matching the supplied schema."
            ),
        },
        {"role": "user", "content": "张三，法律事务部高级总监。"},
    ],
    response_format={
        "type": "json_schema",
        "json_schema": {
            "name": "info_extraction",
            "schema": schema,
        },
    },
    max_tokens=512,
)

result = json.loads(completion.choices[0].message.content)
print(result)
```

XGrammar constrains structure, not meaning. Keep explicit instructions and
enough `max_tokens` for all required fields.

## Anthropic Compatibility

```bash
pip install anthropic
```

PowerShell:

```powershell
$env:ANTHROPIC_BASE_URL = "https://chat.ecnu.edu.cn/open/api/anthropic"
$env:ANTHROPIC_AUTH_TOKEN = $env:ECNU_API_KEY
```

macOS or Linux:

```bash
export ANTHROPIC_BASE_URL="https://chat.ecnu.edu.cn/open/api/anthropic"
export ANTHROPIC_AUTH_TOKEN="$ECNU_API_KEY"
```

```python
import anthropic

anthropic_client = anthropic.Anthropic()

message = anthropic_client.messages.create(
    model="ecnu-plus",
    max_tokens=1000,
    system="You are a helpful assistant.",
    messages=[
        {
            "role": "user",
            "content": [{"type": "text", "text": "你好。"}],
        }
    ],
)

print(message.content)
```

For an Anthropic tool that relies on the model name to recognize the larger
context window:

```python
message = anthropic_client.messages.create(
    model="ecnu-max[1m]",
    max_tokens=1000,
    messages=[{"role": "user", "content": "Summarize the long context."}],
)
```

The suffix is specific to the Anthropic compatibility layer. `opus` names map
to `ecnu-max`; `sonnet`, `haiku`, and other unrecognized names map to
`ecnu-plus`.

## Model Discovery

```python
models = client.models.list()
for model in models.data:
    print(model.id, model.owned_by)
```

Use the response to discover current IDs, then use the model documentation to
interpret aliases, vision support, thinking defaults, and pricing.

## HTTP Error Handling

`detail` may be a string or a validation-error array. Preserve both forms:

```python
def raise_ecnu_error(response):
    if response.ok:
        return

    try:
        payload = response.json()
    except ValueError:
        payload = None

    if isinstance(payload, dict) and "detail" in payload:
        detail = payload["detail"]
    else:
        detail = response.text[:1000]

    raise RuntimeError(f"ECNU API HTTP {response.status_code}: {detail}")
```

Interpret common statuses before retrying:

- `401`: fix token handling; do not retry unchanged credentials.
- `403`: verify the application's IP allowlist.
- `422`: inspect JSON field type and `detail[].loc`; splitting a genuinely
  oversized batch may help, but blind retry does not.
- `429`: stop concurrent calls, inspect credits, then retry later with backoff.

## Sequential Workloads

Do not use a thread pool or `asyncio.gather` for ECNU batches. Process one
request at a time and keep enough information to resume safely:

```python
results = []
for index, prompt in enumerate(prompts):
    completion = client.chat.completions.create(
        model="ecnu-plus",
        messages=[{"role": "user", "content": prompt}],
    )
    results.append(
        {
            "index": index,
            "content": completion.choices[0].message.content,
        }
    )
```

Sequential calls improve stability and make `429` recovery, credit accounting,
and partial-result persistence easier to reason about.
