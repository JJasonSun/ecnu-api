# Official endpoint map

Use this as a router, not a second copy of ECNU's parameter tables. Open the
page for the requested capability; there is no prerequisite to read every page.
The small local recipes cover integration details that otherwise get rediscovered.

## Protocol roots

| Client / integration | Base or full URL |
|---|---|
| OpenAI-compatible | `https://chat.ecnu.edu.cn/open/api/v1` |
| Anthropic-compatible base | `https://chat.ecnu.edu.cn/open/api/anthropic` |
| Anthropic messages | `https://chat.ecnu.edu.cn/open/api/anthropic/v1/messages` |
| Embed ticket endpoint | `https://chat.ecnu.edu.cn/open/api/embed/app` |

Do not concatenate the Anthropic path onto the OpenAI base. Keep credentials
in environment variables; ticket URLs are also credentials.

## Pick the contract for the task

| Task | Official documentation | Local addition when needed |
|---|---|---|
| Chat, streaming, tools, image understanding | [Chat Completions](https://developer.ecnu.edu.cn/vitepress/llm/api/completions.html) | [Thinking/tool history](examples.md#thinking-and-tool-history) |
| Responses-compatible client | [Responses](https://developer.ecnu.edu.cn/vitepress/llm/api/responses.html) | Verify the specific advanced tool/event support; compatibility alone is insufficient |
| JSON Schema or JSON object output | [Structured output](https://developer.ecnu.edu.cn/vitepress/llm/api/structuredoutput.html) | Check completion, parse raw JSON, and validate the supplied schema; do not hide a mismatch by stripping fences |
| Embeddings | [Text vectors](https://developer.ecnu.edu.cn/vitepress/llm/api/embedding.html) | [Raw-string LangChain recipe](examples.md#langchain-embeddings) |
| Rerank | [Rerank](https://developer.ecnu.edu.cn/vitepress/llm/api/rerank.html) | Use the endpoint's contract, not an assumed OpenAI SDK method |
| Image generation | [Images](https://developer.ecnu.edu.cn/vitepress/llm/api/imagegenerate.html) | Observe the current URL lifetime and avoid duplicate paid generations |
| Text-to-speech | [Audio](https://developer.ecnu.edu.cn/vitepress/llm/api/audio.html) | [Non-JSON errors and PCM headers](workflows.md#start-from-the-symptom) |
| Model discovery | [Models endpoint](https://developer.ecnu.edu.cn/vitepress/llm/api/models.html) | A visible ID does not prove usable capability or valid authentication |
| Anthropic-compatible client | [Anthropic API](https://developer.ecnu.edu.cn/vitepress/llm/api/anthropic.html) | [SDK setup](examples.md#anthropic-sdk); investigate suffix errors only when they occur |
| Embed an iframe | [Embed integration](https://developer.ecnu.edu.cn/vitepress/llm/api/embediframe.html) | Do not log or reuse one-time tickets |
| Browser link that submits a question | [URL chat](https://developer.ecnu.edu.cn/vitepress/llm/api/urlchat.html) | Opening a submit link sends data; do not auto-open it as a documentation check |

## Account and changing values

Use [model/account pointers](models.md) for models, thinking, current pricing,
quotas, credentials, data handling, and release notes. Do not maintain duplicate
copies of those changing tables here.

When documentation and behavior disagree, use the matching
[dated deviation](known_deviations.md). The current official page is the
contract; a dated observation describes one tested environment. Neither a
model card nor an accepted over-limit request establishes an ECNU API limit.
