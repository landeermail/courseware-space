# 待裁决清单

## 2026-07-28：Kimi API key 验证失败

- 初始证据：任务 0 执行环境检查返回 `KIMI_API_KEY_PRESENT=no`。
- 最新证据：收到临时 key 后，按 Kimi 官方文档向 `https://api.moonshot.cn/v1/chat/completions` 使用 `kimi-k2.6` 发出一次 hello 级请求，返回 HTTP `401`，错误类型为 `invalid_authentication_error`，消息为 `Invalid Authentication`。
- 安全处理：key 未写入文件、仓库或日志，验证进程结束前已清除环境变量。
- 影响：无法执行任务 2（真实 Kimi 解析调用与端到端生成）、任务 3（20 题真实成功率）和任务 4（真实生成演示全流程）。
- 当前处理：任务 1 已完成；严格停止生成相关任务，不更换供应商、不尝试未确认通道、不连接本机 Codex 代理、不伪造 API 结果。
- 解除条件：从 Kimi 开放平台重新创建或确认一个适用于 Moonshot 官方 Chat Completions API 的有效 key，放入本地环境变量 `KIMI_API_KEY` 后重新执行 hello 级请求。
