# ECNU API Examples

These examples use environment variables, explicit request shapes, and
sequential calls. They avoid undocumented parameters.

The OpenAI SDK chat, Responses, and embedding paths, the Anthropic SDK
`ecnu-plus` path, and the LangChain embedding path below were live-verified on
**2026-08-23** with Python 3.9.6, OpenAI 2.48.0, Anthropic 0.125.0, and
langchain-openai 0.3.35. This is dated compatibility evidence, not a guarantee
for other versions.

## Setup

```bash
python3 -m pip install openai requests
export ECNU_API_KEY="your-api-key"
```

```python
import os
from openai import OpenAI

api_key = os.environ["ECNU_API_KEY"]

client = OpenAI(
    api_key=api_key,
    base_url="https://chat.ecnu.edu.cn/open/api/v1",
    timeout=60.0,
    max_retries=0,
)
```

Disabling SDK retries prevents an ambiguous POST failure from being submitted
again. Treat such a transport failure as inconclusive.

## Chat Completions

```python
completion = client.chat.completions.create(
    model="ecnu-plus",
    messages=[
        {"role": "system", "content": "Answer accurately and concisely."},
        {"role": "user", "content": "用一句话介绍华东师范大学。"},
    ],
)

if not completion.choices:
    raise RuntimeError("chat response contained no choices")
content = completion.choices[0].message.content or ""
print(content)
```

## Responses API

```python
response = client.responses.create(
    model="ecnu-max",
    input="用一句话介绍华东师范大学。",
)

text = getattr(response, "output_text", None) or ""
if not text:
    raise RuntimeError("response contained no text output")
print(text)
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

if not completion.choices:
    raise RuntimeError("thinking response contained no choices")
message = completion.choices[0].message
answer = message.content or ""
print(answer)
```

Do not print or persist hidden reasoning. Keep `reasoning_content` only in
memory when it is required for the immediately following tool-using turn, then
discard it.

## Streaming

```python
stream = client.chat.completions.create(
    model="ecnu-plus",
    messages=[{"role": "user", "content": "Tell me a short story."}],
    stream=True,
)

for chunk in stream:
    choices = getattr(chunk, "choices", None) or []
    if not choices:  # Usage-only and keepalive chunks may have no choices.
        continue
    text = getattr(choices[0].delta, "content", None)
    if text:
        print(text, end="", flush=True)
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

if not completion.choices:
    raise RuntimeError("tool response contained no choices")
for call in getattr(completion.choices[0].message, "tool_calls", None) or []:
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

if not completion.choices:
    raise RuntimeError("vision response contained no choices")
print(completion.choices[0].message.content or "")
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

if not response.data:
    raise RuntimeError("embedding response contained no vectors")
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
if len(vectors) != len(texts):
    raise RuntimeError("embedding response count did not match input count")
assert all(len(vector) == 1024 for vector in vectors)
```

Do not send integer token IDs.

### LangChain embeddings

```bash
python3 -m pip install langchain-openai
```

```python
from langchain_openai import OpenAIEmbeddings

embeddings = OpenAIEmbeddings(
    base_url="https://chat.ecnu.edu.cn/open/api/v1",
    api_key=api_key,
    model="ecnu-embedding-small",
    check_embedding_ctx_length=False,
    timeout=60.0,
    max_retries=0,
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

This call consumes credits. Do not run it merely to validate code. Use a
one-time URL only in memory and transfer the response to controlled storage
before its 24-hour expiry.

```python
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import urlsplit

import requests

response = client.images.generate(
    model="ecnu-image",
    prompt="水墨风，竹林，渔船，湖泊，带斗笠的老翁",
    size="1024x1024",
    response_format="url",
)

item = response.data[0] if response.data else None
image_url = getattr(item, "url", None)
if not image_url:
    raise RuntimeError("image response contained no URL")

approved_hosts = {
    host.strip().lower()
    for host in os.environ["APPROVED_IMAGE_HOSTS"].split(",")
    if host.strip()
}
parsed_url = urlsplit(str(image_url))
hostname = parsed_url.hostname
if parsed_url.scheme.lower() != "https" or not hostname or hostname.lower() not in approved_hosts:
    raise RuntimeError("image URL host is not approved")

target = Path(".live-artifacts") / "generated-image.bin"
target.parent.mkdir(parents=True, exist_ok=True)
temporary = None
max_image_bytes = 20 * 1024 * 1024  # Application policy, not an ECNU limit.
try:
    try:
        with requests.get(
            str(image_url), stream=True, timeout=(5, 60), allow_redirects=False
        ) as download:
            if download.is_redirect:
                raise RuntimeError("redirect target requires separate validation")
            download.raise_for_status()
            media_type = download.headers.get("Content-Type", "").split(";", 1)[0]
            if not media_type.startswith("image/"):
                raise RuntimeError("download did not return an image")
            with NamedTemporaryFile("wb", dir=target.parent, delete=False) as output:
                temporary = Path(output.name)
                total = 0
                for block in download.iter_content(64 * 1024):
                    if not block:
                        continue
                    total += len(block)
                    if total > max_image_bytes:
                        raise RuntimeError("download exceeded the application limit")
                    output.write(block)
                if total == 0:
                    raise RuntimeError("download returned an empty image")
    except requests.RequestException:
        raise RuntimeError("image download failed") from None
    temporary.replace(target)
finally:
    if temporary is not None and temporary.exists():
        temporary.unlink()
```

Do not print or log `image_url`. Configure `APPROVED_IMAGE_HOSTS` from an
application-owned egress policy and validate every redirect separately. Do not
retry generation after an ambiguous timeout.

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

response.stream_to_file(".live-artifacts/output.mp3")
```

Multiple texts require separate sequential calls. They are not one batch API
request.

## Structured output

Both `ecnu-plus` and `ecnu-max` support this `json_schema` request. The
schema and JSON-object examples here follow the current documentation;
they are not included in the dated SDK live-verification claim above.

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

if not completion.choices or not completion.choices[0].message.content:
    raise RuntimeError("structured response contained no content")
if completion.choices[0].finish_reason != "stop":
    raise RuntimeError("structured response did not finish normally")
result = json.loads(completion.choices[0].message.content)
if not isinstance(result, dict) or not all(
    isinstance(result.get(field), str) for field in schema["required"]
):
    raise RuntimeError("structured response did not match the extraction schema")
print(result)
```

For JSON-object output without a supplied schema:

```python
completion = client.chat.completions.create(
    model="ecnu-max",
    messages=[{"role": "user", "content": 'Return a JSON object with status "ok".'}],
    response_format={"type": "json_object"},
    max_tokens=128,
)
if not completion.choices or completion.choices[0].finish_reason != "stop":
    raise RuntimeError("JSON response did not finish normally")
content = completion.choices[0].message.content
if not content:
    raise RuntimeError("JSON response contained no content")
result = json.loads(content)
if not isinstance(result, dict):
    raise RuntimeError("JSON response was not an object")
print(result)
```

Do not strip Markdown fences before parsing. `json_object` does not guarantee
the `status` field or its value; validate application-specific requirements
separately. For more complex schemas, use a JSON Schema validator.

## URL-parameter chat

Build a link without navigating to it:

```javascript
const question = "Hello";
const url = `https://chat.ecnu.edu.cn/html/#/chat?submit=${encodeURIComponent(question)}`;
```

Opening `url` creates a new ChatECNU conversation and sends the question once,
after school SSO if needed. It is not an API call and takes no API key. Avoid
confidential questions in links that can be stored or shared.

## Anthropic compatibility

```bash
python3 -m pip install anthropic
```

```python
import os

import anthropic

anthropic_client = anthropic.Anthropic(
    api_key=os.environ["ECNU_API_KEY"],
    base_url="https://chat.ecnu.edu.cn/open/api/anthropic",
    timeout=60.0,
    max_retries=0,
)

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

text = "".join(
    block.text
    for block in message.content
    if getattr(block, "type", None) == "text"
)
print(text)
```

Use plain `ecnu-max` by default. Only try `ecnu-max[1m]` when an Anthropic tool
must recognize the long-context suffix:

```python
def create_long_context_message(
    client, messages, *, plain_max_previously_verified=False
):
    try:
        return client.messages.create(
            model="ecnu-max[1m]",
            max_tokens=1000,
            messages=messages,
        )
    except anthropic.AuthenticationError as exc:
        if exc.status_code != 401 or not plain_max_previously_verified:
            raise
        return client.messages.create(
            model="ecnu-max",
            max_tokens=1000,
            messages=messages,
        )
```

Use this one-shot fallback only after plain `ecnu-max` has already succeeded
with the same credential and the caller accepts losing the `[1m]` capability
signal. Log only that the fallback occurred, never the prompt, credential, or
error body.

## Error handling

Preserve JSON error structure, tolerate non-JSON errors, and retain only a
bounded, redacted sample plus an allowlisted request ID:

```python
import json
import re

SENSITIVE_KEYS = {
    "authorization", "x_api_key", "api_key", "auth_token", "token",
    "access_token", "client_secret", "ticket", "reasoning_content",
    "messages", "input", "prompt", "content", "url", "download_url",
    "image_url", "b64_json", "base64", "audio", "data",
}
SECRET_TEXT = re.compile(
    r"(?i)(bearer\s+)[^\s\"']+|\bsk-[A-Za-z0-9_-]{8,}\b|"
    r"https?://[^\s\"']+|data:[^,\s]+;base64,[A-Za-z0-9+/=_-]+"
)


def sanitize_error(value):
    if isinstance(value, dict):
        return {
            str(key): (
                "[REDACTED]"
                if str(key).lower().replace("-", "_") in SENSITIVE_KEYS
                else sanitize_error(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [sanitize_error(item) for item in value]
    if isinstance(value, str):
        return SECRET_TEXT.sub("[REDACTED]", value)
    return value


def bounded_error_sample(response, limit=1000):
    try:
        value = response.json()
        sample = json.dumps(sanitize_error(value), ensure_ascii=False)
    except ValueError:
        sample = SECRET_TEXT.sub("[REDACTED]", response.text)
    return sample if len(sample) <= limit else sample[: limit - 14] + "...[truncated]"


def raise_ecnu_error(response):
    if response.ok:
        return

    request_id = next(
        (
            response.headers.get(name)
            for name in ("X-Request-ID", "Request-ID", "X-Trace-ID")
            if response.headers.get(name)
        ),
        "unavailable",
    )
    raise RuntimeError(
        f"ECNU API HTTP {response.status_code} "
        f"request_id={str(request_id)[:200]}: {bounded_error_sample(response)}"
    )
```

Do not retry unchanged credentials after `401`. For `422`, inspect field paths
and types. For `429`, stop concurrency, inspect credits, then use bounded
backoff. Do not blindly retry billable calls after an ambiguous timeout.
