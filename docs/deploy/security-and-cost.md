# 当前安全与成本护栏

## 已落实

- 正式课件是公开静态内容，GitHub Pages 是唯一生产渠道；公开仓库不保存 Kimi key、云 AccessKey 或老师长期凭证明文。
- 公网 FC 只运行 feedback-only 包，环境变量白名单不含 Kimi；生成、媒体、任务和产物路由为 404。
- 老师原长期链接是当前唯一评价凭证，FC 精确比较；部署不得轮换链接。fragment 不随 Pages HTTP 请求发送，页面读取后写入 `sessionStorage` 并清除地址栏。
- 反馈任务绑定精确 revision；状态和历史来自服务端，不以 `localStorage` 为事实源。
- 运行 role 只允许 `feedback/*` 追加写、`feedback/tasks/*` 与 `feedback/reviews/*` 读取及条件列举；没有删除、ACL、其他 bucket 或模型权限。
- 部署使用专用最小权限 RAM 用户；部署入口拒绝 root。FC 保留并发 1，应用按单客户端 30 次/10 分钟、全局 80 次/10 分钟限流；CORS 精确允许 GitHub Pages Origin。
- feedback-only ZIP 采用白名单构建并扫描 Kimi/生成器引用；代码对象按 SHA-256 存放，便于精确回滚。
- 2026-08-20，临时 Root AccessKey 的本机副本和云端对象均已删除；生产部署继续使用最小权限 RAM 用户。

## 仍待处理

- “持有链接即本人”只适合当前单老师开发阶段。出现第二位老师或公开产品化前，重新设计身份、凭证恢复、持久限流与审计，不能继续共享或复制当前方案。
- Kimi Code 只用于私人研发。对公众开放生成或收费前，迁移到 Kimi Platform，或取得产品后端用途的明确书面许可，并重新核价。

## 不构成安全边界

- CORS 不能替代身份认证；
- 随机 Pages 路径不能保护公开课件内容；
- GitHub 仓库私有化不能保护已发送到浏览器的凭证；
- 内部测试或安全审查不能替代老师真实入口门禁。
