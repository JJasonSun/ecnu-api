# ECNU Skill 实用化改版验收

改版目标是减少重复配置、文档查找和兼容性误判。日常接入从
[SKILL.md](../SKILL.md) 开始；官方契约、针对性配方、历史偏差和仓库维护各有入口。
本文件保留改版的验收证据，原接续步骤已经完成，不是下一次使用的待办清单。

## 2026-09-12 离线验收

环境：Codex CLI 0.153.4、`gpt-6-astra` / `medium`、Python 3.9.6，
OpenAI 2.48.0、Anthropic 0.125.0、LangChain OpenAI 0.3.35、HTTPX 0.28.1。
三个合成项目分别使用独立会话和本分支 Skill，禁用旧全局版及网络请求。

| 任务 | 检查结果 |
|---|---|
| 普通 Python 接入 | 保留原函数，配置 ECNU 地址、模型、超时和不自动重试；4 项离线测试通过 |
| LangChain Embedding | 实际请求保留原始字符串，不发送 `dimensions`；数量与 1024 维检查通过，共 5 项测试 |
| `/models` 空列表失败样例 | `200` 空/非空列表都不作为鉴权成功证据；4 项离线测试通过 |

三次均未索要密钥、反复确认或执行平台全量 smoke、Skill 仓库维护流程。
Embedding 与 Anthropic 入口分别直达对应章节；新增导航只校验了链接，未重复 Agent 会话。
OpenAI SDK 工具消息转换配方由一项回归测试覆盖：完整保留 `reasoning_content`、
`reasoning` 或两者均不存在时的实际返回字段，并检查工具结果和后续用户轮次。

67 项仓库测试、仓库验证器、`skills-ref`、Python 编译、Markdown 链接与锚点、
代码块语法和 `git diff --check` 通过。维护命令见 [AGENTS.md](../AGENTS.md)。

## 2026-09-12 实网验收

获授权后直接执行本分支示例和工具历史片段，完成 8 个串行请求（6 POST、2 GET），
每个请求只执行一次。Python、LangChain Embedding、Anthropic 和 Max 工具三轮续接通过；
无效令牌的 `/models` 请求复现 `200` 空列表偏差。

版本、实际请求字段、返回形状及费用估算以
[实测记录](../references/known_deviations.md#verified-recipe-coverage-on-2026-09-12) 为准。

## 验证边界

这些结果只覆盖所列版本、合成输入与任务，不构成跨 Agent、跨模型或任意框架的效果承诺。
账号实际扣减未核对；其他历史样例没有因本次检查而更新日期或状态。
新增场景出现具体障碍时再补对应配方或检查，不预先扩展模型矩阵和通用教程。
