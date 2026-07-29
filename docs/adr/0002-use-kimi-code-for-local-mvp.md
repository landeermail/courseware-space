# ADR 0002：本地 MVP 使用 Kimi Code，保留供应商迁移边界

- 状态：已采纳；模型选择由 ADR 0004 演进
- 日期：2026-07-28

## 背景

Kimi Code 与 Kimi 开放平台是两套独立系统，API Key、Base URL 和模型 ID 不互通。项目当前取得的是 Kimi Code 会员密钥，正确的 OpenAI 兼容 Base URL 为 `https://api.kimi.com/coding/v1`，可用基础模型 ID 为 `kimi-for-coding`。

Kimi Code 官方将会员 API 主要定位为终端、IDE Agent 和第三方开发工具接入，并建议产品集成使用 Kimi 开放平台。本项目的四周目标是本地现场演示，但长期目标包含商业化。

## 决策

- 本地 MVP 和现场演示使用 Kimi Code 的 OpenAI 兼容 Chat Completions 接口。
- 后端只通过 provider 接口依赖 Kimi，模板、校验、任务队列和落盘逻辑不得依赖特定模型字段。
- 默认模型使用所有会员均可调用的 `kimi-for-coding`；不依赖 K3、高速版或未确认权限。
- API Key 只从后端环境变量读取，永不进入浏览器、生成产物、日志或仓库。
- 请求使用项目真实 `User-Agent`，不伪装成 Codex、Claude Code 或其他客户端。
- 商业上线前必须迁移到 Kimi 开放平台或取得 Kimi 对该产品用途的明确许可。

## 结果

- 当前可以完成无云账号的本地演示和真实成功率测试。
- GitHub Pages 仍只能托管静态前端与生成产物，不能承载 Python 生成服务。
- provider 边界会增加少量代码，但避免将会员制编程接口固化为产品基础设施。
