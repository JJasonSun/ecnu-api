# ECNU API Code Examples

## Table of Contents

- [Setup](#setup)
- [Basic Chat Completion](#basic-chat-completion)
- [Streaming Chat](#streaming-chat)
- [Tool Calling](#tool-calling)
- [Vision Multimodal Chat](#vision-multimodal-chat)
- [Embeddings](#embeddings)
- [LangChain Embeddings](#langchain-embeddings)
- [Rerank](#rerank)
- [Image Generation](#image-generation)
- [Text-to-Speech](#text-to-speech)
- [Model List](#model-list)
- [Thinking Mode](#thinking-mode)
- [Structured Output](#structured-output)
- [Anthropic SDK](#anthropic-sdk)
- [Direct HTTP](#direct-http)

---

## Setup

```bash
pip install openai
```

```python
from openai import OpenAI

client = OpenAI(
    api_key="your-api-key",
    base_url="https://chat.ecnu.edu.cn/open/api/v1",
)
```

## Basic Chat Completion

```python
completion = client.chat.completions.create(
    model="ecnu-plus",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "你是谁？"},
    ],
)

print(completion.choices[0].message.content)
```

## Streaming Chat

```python
stream = client.chat.completions.create(
    model="ecnu-plus",
    messages=[{"role": "user", "content": "Tell me a short story."}],
    stream=True,
)

for chunk in stream:
    delta = chunk.choices[0].delta.content
    if delta:
        print(delta, end="")
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
    print(call.function.name)
    print(call.function.arguments)
```

## Vision Multimodal Chat

Use `ecnu-plus` for new vision integrations. `ecnu-vl` is a compatibility alias
seen in older examples.

```python
import base64

with open("image.jpg", "rb") as f:
    image_base64 = base64.b64encode(f.read()).decode("utf-8")

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
                        "url": f"data:image/jpeg;base64,{image_base64}"
                    },
                },
            ],
        }
    ],
)

print(completion.choices[0].message.content)
```

Public image URL:

```python
completion = client.chat.completions.create(
    model="ecnu-plus",
    messages=[
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Describe this image."},
                {"type": "image_url", "image_url": {"url": "https://example.com/image.jpg"}},
            ],
        }
    ],
)
```

## Embeddings

```python
response = client.embeddings.create(
    model="ecnu-embedding-small",
    input=["干得不错", "一块石头"],
)

for item in response.data:
    print(item.index, len(item.embedding))
```

## LangChain Embeddings

LangChain may tokenize input using OpenAI token IDs unless
`check_embedding_ctx_length=False` is set.

```python
from langchain_openai import OpenAIEmbeddings

embeddings = OpenAIEmbeddings(
    base_url="https://chat.ecnu.edu.cn/open/api/v1",
    api_key="your-api-key",
    model="ecnu-embedding-small",
    dimensions=1024,
    check_embedding_ctx_length=False,
)

print(embeddings.embed_query("Hello world"))
```

## Rerank

Rerank is Cohere-compatible. Use direct HTTP if your OpenAI SDK does not expose
rerank.

```python
import requests

response = requests.post(
    "https://chat.ecnu.edu.cn/open/api/v1/rerank",
    headers={
        "Authorization": "Bearer your-api-key",
        "Content-Type": "application/json",
    },
    json={
        "model": "ecnu-rerank",
        "query": "介绍华东师范大学",
        "documents": [
            "华东师范大学是教育部直属并与上海市重点共建的综合性研究型大学。",
            "量子计算是计算科学的一个前沿领域。",
            "师大校训为求实创造，为人师表。",
        ],
        "return_documents": True,
        "top_n": 3,
    },
    timeout=60,
)

response.raise_for_status()
for result in response.json()["results"]:
    print(result["index"], result["relevance_score"])
    print(result.get("document", "")[:80])
```

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

Download or transfer URL responses within 24 hours.

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

Direct HTTP:

```python
import requests

response = requests.post(
    "https://chat.ecnu.edu.cn/open/api/v1/audio/speech",
    headers={
        "Authorization": "Bearer your-api-key",
        "Content-Type": "application/json",
    },
    json={
        "model": "ecnu-tts",
        "input": "你好，欢迎使用文本转语音服务。",
        "voice": "xiayu",
        "response_format": "mp3",
        "speed": 1.0,
    },
    timeout=60,
)

response.raise_for_status()
with open("output.mp3", "wb") as f:
    f.write(response.content)
```

## Model List

```python
models = client.models.list()
for model in models.data:
    print(model.id, model.owned_by)
```

## Thinking Mode

Pass ECNU's custom `thinking` field through `extra_body` when using the OpenAI
Python SDK.

```python
completion = client.chat.completions.create(
    model="ecnu-max",
    messages=[{"role": "user", "content": "Analyze this complex problem."}],
    extra_body={"thinking": {"type": "enabled"}},
)

message = completion.choices[0].message
reasoning = getattr(message, "reasoning_content", None)
if reasoning:
    print("Reasoning:", reasoning)
print("Answer:", message.content)
```

## Structured Output

```python
import json

schema = {
    "name": "info_extraction",
    "schema": {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "department": {"type": "string"},
            "title": {"type": "string"},
        },
        "required": ["name", "department", "title"],
    },
}

completion = client.chat.completions.create(
    model="ecnu-plus",
    messages=[
        {
            "role": "system",
            "content": "Extract name, department, and title. Return valid JSON.",
        },
        {"role": "user", "content": "张三，法律事务部高级总监。"},
    ],
    response_format={
        "type": "json_schema",
        "json_schema": schema,
    },
    max_tokens=512,
)

result = json.loads(completion.choices[0].message.content)
print(result)
```

## Anthropic SDK

```bash
pip install anthropic
```

```python
import anthropic
import os

os.environ["ANTHROPIC_BASE_URL"] = "https://chat.ecnu.edu.cn/open/api/anthropic"
os.environ["ANTHROPIC_AUTH_TOKEN"] = "your-api-key"

client = anthropic.Anthropic()

message = client.messages.create(
    model="ecnu-plus",
    max_tokens=1000,
    system="You are a helpful assistant.",
    messages=[
        {
            "role": "user",
            "content": [{"type": "text", "text": "你好啊"}],
        }
    ],
)

print(message.content)
```

## Direct HTTP

```python
import requests

url = "https://chat.ecnu.edu.cn/open/api/v1/chat/completions"
headers = {
    "Authorization": "Bearer your-api-key",
    "Content-Type": "application/json",
}
payload = {
    "model": "ecnu-plus",
    "messages": [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "你是谁？"},
    ],
}

response = requests.post(url, headers=headers, json=payload, timeout=60)
response.raise_for_status()
print(response.json()["choices"][0]["message"]["content"])
```

Streaming with direct HTTP:

```python
import json
import requests

payload["stream"] = True

with requests.post(url, headers=headers, json=payload, stream=True, timeout=60) as response:
    response.raise_for_status()
    for line in response.iter_lines():
        if not line:
            continue
        text = line.decode("utf-8")
        if not text.startswith("data: "):
            continue
        chunk = text[6:]
        if chunk == "[DONE]":
            break
        parsed = json.loads(chunk)
        delta = parsed["choices"][0]["delta"].get("content", "")
        print(delta, end="")
```
