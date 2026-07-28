# 安全与成本护栏

## 已落实

- 本机部署凭证与 Kimi key 从 macOS 钥匙串临时注入；仓库、部署包、日志不保存真实值。
- FC 不注入主账号长期 AccessKey；只注入任务 role 的临时 STS，role 仅允许向唯一 bucket 的 `staging/*` 执行 `oss:PutObject` / `oss:PutObjectAcl`。
- OSS bucket 为 private，部署代码对象为 private，只有生成产物对象为 public-read；不允许 public-read-write。
- 上传限制：图片 8 MB、PDF 20 MB/6 页；JSON 请求最大 28 MB；参数、MIME、魔数、文件名与路径均做白名单校验。
- FC：0.5 vCPU、内存 1,024 MB、磁盘 512 MB、超时 180 秒、保留并发 1、单实例并发 8、云端生成 worker 1。
- 公网 API 只对白名单 Origin 返回 CORS，当前生产页面来源为 `https://landeermail.github.io`；高成本 POST 接口按单客户端 30 次/10 分钟、全局 80 次/10 分钟限流。
- Kimi 超时/鉴权/限流、模板越界、OSS 发布失败和低置信视觉结果都有明确降级，不返回堆栈或 key。

## 上线前仍需落实

- 当前部署控制凭证属于阿里云主账号 root，正式生产前换成最小权限 RAM/OIDC 并轮换主账号 AccessKey。
- 匿名 HTTP trigger 只能用于本轮受控演示。CORS 不是身份认证，非浏览器客户端仍能直接请求；公网生产前需增加真实身份、持久化限流和防滥用入口。
- 本轮明确不创建 API Gateway：传统产品退市，云原生 Serverless 当前固定费用约 0.147 元/小时（约 105.84 元/30 天），还需另计请求与公网流量；与当前低频演示不匹配。
- 费用预算告警需要明确月度金额、告警阈值和接收人。没有这些信息时不擅自创建账号级预算或通知联系人；FC 并发上限已经先行限制最坏消耗速度。
- 演示期任务状态在单实例内存中。生产化前迁移到持久 job store，避免实例回收丢任务。
