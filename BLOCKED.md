# 待裁决清单

## 2026-07-30：私有课件长期链接交付（路线 A）

- 无。目标 bucket、前缀权限、一行交付、长期链接与匿名验收均已成立；未新增或触碰 FC、RAM、demo bucket、域名、CDN及其他云资源。

## 2026-07-30：第 1 题六维全过课件

- 无。原稿答案与独立推导一致；C 项原解析的含混表述已用确定的准静态路径计算替代，不构成物理结论冲突。未产生需另行裁决的顺手任务。

## 2026-07-30：好课件六维标准与老师试用工具包

- 无新增待裁决事项。内部试题公开风险已裁决为本地私有包；第 11 题反应式的电荷守恒错误已依据权威资料完成显式勘误，不再阻塞试用。

## 已解除：2026-07-29 Kimi 频限曾达到 100%

- 证据：抛体 5 题正式批次的 15/15 个模型请求在产生输出前返回 HTTP 403；领导随后提供的 Kimi 控制台截图显示周用量 23%、频限明细 100%，并显示约 2 小时 19 分钟后的重置倒计时。
- 归因：这是可恢复的 provider unavailable，不是 API Key 失效，也不是抛体物理模型被 harness 判错；原始 0/5 结果保持不改，诊断另见 `harness/evidence/generated/projectile/provider-diagnosis.json`。
- 解除证据：频限恢复后 K3＋JSON Mode 探针成功；新的不可覆盖证据完成抛体 5/5、圆周 5/5、两领域各 3 类故障红→绿和逐件浏览器验收，`harness/audit_acceptance.py` 返回 `passed`。
- 保留措施：quota/authentication/permission/configuration/read-timeout/output-limit 仍在首次出现时停止单题和批次；Extra Usage 保持关闭，不以自动付费续跑。

## 已裁决：本轮取消 API Gateway，采用 Pages 直连 FC JSON API

- 证据：FC 默认域名健康检查为 HTTP 200，但响应强制 `Content-Disposition: attachment`。阿里云 2026-07-17 官方公告明确：传统 API 网关将于 2026-08-23 停止新购、2027-03-21 停止续订和版本更新、2027-09-21 全面停止服务，并建议迁移至云原生 API 网关。
- 安全复核：传统 API 网关已开通，但精确查询 `courseware-space-generator` API 组为 0，尚未创建任何传统网关资源，无迁移或清理负担。
- 成本结论：云原生 API 网关 Serverless 当前固定 0.147 元/小时，30 天约 105.84 元，另计请求与公网流量；不符合低频演示的成本目标。
- 裁决：不创建传统或云原生 API Gateway。GitHub Pages 继续承载前端，仅以跨域 `fetch` 调用 FC JSON API；OSS 承载可直接打开的生成结果。
- 安全边界：FC CORS 只允许 `https://landeermail.github.io`，高成本 POST 接口加入进程内单客户端/全局限流，FC 保留并发 1。此方案是受控演示入口，不冒充具备登录鉴权的生产架构。
- 资源复核：传统 API Gateway API 组为 0，云原生网关实例为 0，无需清理。

## 已解除：阿里云账号的 OSS 服务曾处于 UserDisable 状态

- 证据：从零部署首次写操作 `PutBucket courseware-space-demo-10794778` 返回 HTTP 403、错误码 `UserDisable`；脚本立即停止。
- 安全复核：失败后只读确认 bucket、RAM role、RAM policy、FC function 均为 `missing`，没有产生半成品云资源。
- 解除证据：领导已开通 OSS；同一部署脚本成功创建并验证 private bucket，上传 private FC 代码对象，并完成 FC/RAM 部署。

## 2026-07-28：生产部署凭证需迁移到最小权限 RAM 身份

- 证据：领导提供的 CSV 已按官方字段导入 macOS 钥匙串；STS 只读验证成功，脱敏主体为 `acs:ram::1079********4778:root`，属于阿里云主账号而非 RAM 用户。
- 当前处理：演示部署只在本机临时读取该凭证，不写入仓库、配置或 FC 环境；云端运行时使用本任务专属角色，且只访问 `courseware-space-*` 资源。
- 影响：不阻塞本轮演示部署；正式生产前必须换成最小权限 RAM 部署身份并轮换主账号 AccessKey。
- 待裁决：生产环境采用 RAM 用户、RAM 角色还是 OIDC，需结合后续 CI/CD 方案决定，本轮不扩大范围。

## 已解除：任务 4 页面路径与修改边界冲突

- 任务书“界限”只允许新建 `generator/staging/`，不允许修改既有 `generator/index.html`；任务 4 又明确要求该文件支持文字/图片/PDF 三种输入。
- 解除依据：领导接受 Pages 直连 FC 的统一生成器方案，明确授权继续实现。
- 当前处理：文字、图片与 PDF 已合并到 `generator/index.html`；`server/media_demo.html` 仅保留为开发期独立验证页。

## 2026-07-28：自定义域名待裁决

- 演示阶段按任务书使用 FC/OSS 默认域名，不购买域名、不改 DNS。
- 如需品牌域名，必须另行明确域名、备案和 DNS 操作授权。

## 已生效裁决

- **Kimi 通道**：Kimi Code 通道用于当前私人研发与演示，模型策略由 ADR 0004 固定为 `k3-256k`。2026-07-29 重新核对官方平台边界后，领导确认：产品对公众开放或收费前必须迁移 Kimi Platform，或取得 Kimi 对产品后端用途的明确书面许可；此前“无需迁移”的内部判断不再作为商业上线依据。
- **key 注入方式**：从 macOS 钥匙串临时读取为领导认可的安全方式，不算越权；key 仍不得写入仓库或日志。
- **后端托管**：本轮采用阿里云函数计算 FC + 对象存储 OSS；AccessKey 已从钥匙串完成只读 STS 验证。
