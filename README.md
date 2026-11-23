# ECNU API Agent Skill

[English](#english) · 中文

面向 ECNU / ChatECNU 大模型开放平台的**非官方** Agent Skill：帮助 Agent 接入应用或 SDK、
做好生产环境加固、排查故障，不必每次重新摸索文档没写清的差异。

## 安装与使用

```bash
npx skills add JJasonSun/ecnu-api
```

更新已有的全局安装：

```bash
npx skills update -g ecnu-api
```

示例请求：

```text
使用 $ecnu-api 把这个应用接到 ECNU 上，保留现有框架。
只改接入部分和相关检查，不要发起真实请求。
```

需要实际调用时，通过环境变量或密钥管理工具配置 `ECNU_API_KEY`。
不要把真实密钥贴进对话，也不要提交到仓库。

## 相比官方文档增加了什么

[官方文档](https://developer.ecnu.edu.cn/vitepress/llm/model.html)是权威依据且更新频繁，
所以本 Skill 只链接、不复制，只保留文档没有提供给 Agent 的内容：

| 需求 | 位置 |
|---|---|
| 某个任务该用哪个协议、模型和官方页面 | [SKILL.md](SKILL.md) |
| ECNU 专用的小配方，每个都有离线测试 | [配方](references/examples.md) |
| 生产环境的并发、重试、超时、成本与错误处理 | [工程实践](references/engineering.md) |
| 对现有接入做只读体检或迁移 | [体检](references/audit.md) |
| 当前模型快照与账号相关页面 | [模型](references/models.md) |
| 症状速查、当前实测差异及复现方式 | [排障](references/troubleshooting.md) |

每条实测观察都对应 `scripts/smoke_test.py` 中的一个用例，ECNU 发版后可以复现或撤销。
历史记录留在 Git 里：不再复现的观察会直接删除，不做归档。维护规则见 [AGENTS.md](AGENTS.md)。

## 免责声明

本社区 Skill 未获华东师范大学认可，与其无隶属关系。不要提交凭据、私人提示词、个人数据、
原始实测响应、生成的媒体文件或一次性访问链接。

---

## English

An unofficial Agent skill for building on the ECNU / ChatECNU LLM Open
Platform: connect an application or SDK, harden it for production, and
diagnose failures without rediscovering the same differences each time.

### Install and use

```bash
npx skills add JJasonSun/ecnu-api
```

Update an existing global installation:

```bash
npx skills update -g ecnu-api
```

Example request:

```text
Use $ecnu-api to adapt this application to ECNU. Keep the current framework.
Only change the integration and its relevant checks; do not make live requests.
```

Configure `ECNU_API_KEY` through the environment or a secret manager when
execution is needed. Never paste a real key into chat or commit it.

### What this adds to the official docs

The [official documentation](https://developer.ecnu.edu.cn/vitepress/llm/model.html)
is the contract and changes often, so the skill links to it instead of copying
it, and keeps only what the docs do not give an Agent:

| Need | Where |
|---|---|
| Which protocol, model and official page fit a task | [SKILL.md](SKILL.md) |
| Small ECNU-specific recipes, each covered by an offline test | [Recipes](references/examples.md) |
| Concurrency, retries, timeouts, cost and error handling in production | [Engineering](references/engineering.md) |
| Read-only audit or migration of an existing integration | [Audit](references/audit.md) |
| Current model snapshot and account pages | [Models](references/models.md) |
| Symptoms, current live deviations, and how to rerun them | [Troubleshooting](references/troubleshooting.md) |

Every live observation names a runner case in `scripts/smoke_test.py`, so it
can be reproduced or retired after an ECNU release. History lives in Git:
observations that no longer reproduce are deleted, not archived. Maintainer
rules are in [AGENTS.md](AGENTS.md).

### Disclaimer

This community skill is not endorsed by or affiliated with East China Normal
University. Never commit credentials, private prompts, personal data, raw live
responses, generated media, or one-time access URLs.
