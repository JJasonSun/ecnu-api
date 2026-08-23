# ECNU API Examples

These examples use environment variables, explicit request shapes, and
sequential calls. They avoid undocumented parameters.

## Setup

```bash
pip install openai requests
export ECNU_API_KEY="your-api-key"
```

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

## Responses API

```python
response = client.responses.create(
    model="ecnu-max",
    input="用一句话介绍华东师范大学。",
)

print(response.output_text)
```

Start with text input. Verify advanced Responses tools and streaming events
before depending on them.

## Thinking mode

Pass ECNU extensions through `extra_body`:

```python
completion = client.chat.completions.create(
    model="ecnu-max",
    messages=[{"role": "user", "content": "Analyze this problem."}],
    extra_body={
        "thinking": {"type": "enabled"},
        "reasoning_effort": "high",
    },
)

message = completion.choices[0].message
answer = message.content
print(answer)
```

Do not print hidden reasoning in user-facing applications. Preserve
`reasoning_content` only when required for a subsequent tool-using turn.

## Streaming

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

## Tool calling

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
                    "location": {"type": "string"},
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

for call in completion.choices[0].message.tool_calls or []:
    print(call.id, call.function.name, call.function.arguments)
```

The caller must execute the function and submit the tool result in a subsequent
turn.

## Vision

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

For a local image, base64-encode it into a data URL. Do not assume undocumented
image-count, byte-size, or pixel limits.

## Embeddings

One text:

```python
response = client.embeddings.create(
    model="ecnu-embedding-small",
    input="华东师范大学",
)

vector = response.data[0].embedding
assert len(vector) == 1024
```

Several texts in one request:

```python
texts = [
    "华东师范大学是综合性研究型大学。",
    "量子计算是计算科学的前沿领域。",
]

if not texts or not all(isinstance(text, str) for text in texts):
    raise TypeError("input must be a non-empty string array")

response = client.embeddings.create(
    model="ecnu-embedding-small",
    input=texts,
)

ordered = sorted(response.data, key=lambda item: item.index)
vectors = [item.embedding for item in ordered]
assert all(len(vector) == 1024 for vector in vectors)
```

Do not send integer token IDs.

### LangChain embeddings

```bash
pip install langchain-openai
```

```python
from langchain_openai import OpenAIEmbeddings

embeddings = OpenAIEmbeddings(
    base_url="https://chat.ecnu.edu.cn/open/api/v1",
    api_key=api_key,
    model="ecnu-embedding-small",
    check_embedding_ctx_length=False,
)

vector = embeddings.embed_query("Hello world")
assert len(vector) == 1024
```

`check_embedding_ctx_length=False` prevents LangChain from converting strings
to OpenAI token IDs. Validate the fixed output size after the response; do not
send a dimension-selection request field that ECNU does not document.

For many texts, use conservative sequential batches:

```python
def chunks(items, size):
    for start in range(0, len(items), size):
        yield items[start : start + size]


all_vectors = []
for batch in chunks(texts, size=16):  # Application policy, not an ECNU limit.
    response = client.embeddings.create(
        model="ecnu-embedding-small",
        input=batch,
    )
    ordered = sorted(response.data, key=lambda item: item.index)
    all_vectors.extend(item.embedding for item in ordered)
```

## Rerank

The OpenAI SDK has no rerank resource, so use direct HTTP:

```python
import requests

documents = [
    "华东师范大学是教育部直属的综合性研究型大学。",
    "量子计算是计算科学的前沿领域。",
]
top_n = 2

if not documents or not all(isinstance(doc, str) for doc in documents):
    raise TypeError("documents must be a non-empty string array")
if any(len(doc) > 8192 for doc in documents):
    raise ValueError("each document must be at most 8192 characters")
if not 1 <= top_n <= len(documents):
    raise ValueError("application policy requires a valid result count")

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
```

The local `top_n` check is application policy, not a published ECNU maximum.

## Image generation

This call consumes credits. Do not run it merely to validate code.

```python
response = client.images.generate(
    model="ecnu-image",
    prompt="水墨风，竹林，渔船，湖泊，带斗笠的老翁",
    size="1024x1024",
    response_format="url",
)

print(response.data[0].url)
```

Transfer URL results before their 24-hour expiry. Do not blindly retry after an
ambiguous timeout.

## Text-to-speech

This call consumes credits:

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

Multiple texts require separate sequential calls. They are not one batch API
request.

## Structured output

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
            "content": "Extract name, department, and title.",
        },
        {
            "role": "user",
            "content": "张三，法律事务部高级总监。",
        },
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

## Anthropic compatibility

```bash
pip install anthropic
export ANTHROPIC_BASE_URL="https://chat.ecnu.edu.cn/open/api/anthropic"
export ANTHROPIC_AUTH_TOKEN="$ECNU_API_KEY"
```

```python
import anthropic

anthropic_client = anthropic.Anthropic()

message = anthropic_client.messages.create(
    model="ecnu-plus",
    max_tokens=1000,
    messages=[
        {
            "role": "user",
            "content": [{"type": "text", "text": "你好。"}],
        }
    ],
)

print(message.content)
```

Use plain `ecnu-max` by default. Only try `ecnu-max[1m]` when an Anthropic tool
must recognize the long-context suffix:

```python
def create_long_context_message(client, messages):
    try:
        return client.messages.create(
            model="ecnu-max[1m]",
            max_tokens=1000,
            messages=messages,
        )
    except anthropic.AuthenticationError:
        return client.messages.create(
            model="ecnu-max",
            max_tokens=1000,
            messages=messages,
        )
```

Log the fallback without logging prompts or credentials. The fallback preserves
model access but may not advertise the same context capability to the client.

## Error handling

Preserve string and array forms of `detail`, and tolerate non-JSON errors:

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

    raise RuntimeError(
        f"ECNU API HTTP {response.status_code}: {detail}"
    )
```

Do not retry unchanged credentials after `401`. For `422`, inspect field paths
and types. For `429`, stop concurrency, inspect credits, then use bounded
backoff. Do not blindly retry billable calls after an ambiguous timeout.
