# 阿里云部署工具

当前生产只使用 `server/feedback_app.py` 提供老师评价工作区；公网 FC 不运行 Kimi 或生成器。静态课件由 GitHub Pages 发布，普通课件发布不调用本目录的云脚本。

旧生成服务的 `build_package.sh`、`deploy.sh`、`deploy_from_keychain.sh` 与 `rollback_code.sh` 为历史研发工具，不是当前生产入口。未经新的产品、许可、成本与安全裁决，不得用它们覆盖 feedback-only FC。

## 当前生产资源

- FC function / trigger：`courseware-space-*`，运行 feedback-only 白名单包；
- 代码 OSS bucket：`courseware-space-*`，仅保存内容寻址部署 ZIP；
- 评价 OSS bucket：`courseware-space-private-*`，任务与评价位于 `feedback/tasks/*`、`feedback/reviews/*`；
- RAM deployer / runtime role / policy：`courseware-space-*`；
- GitHub Pages：稳定老师题库、不可变课件 revision 与评价页面。

精确资源名和当前 FC 配置属于受控生产信息，不以仓库文档为事实源。任何写入前都要读取根目录 `BLOCKED.md`，获得部署授权，并使用阿里云 CLI 只读核对目标。

## Feedback-only 部署

前置条件：阿里云 CLI 3.3.0 或更高版本及 `sts`、`fc`、`ram` 插件，Python 3、`jq`、`zip`，以及专用最小权限 RAM deployer。真实部署入口拒绝 root 身份。

```bash
export ALIYUN_CLI="$HOME/.local/bin/aliyun"
export ALIBABA_CLOUD_ACCESS_KEY_ID="$(security find-generic-password -s courseware-space-aliyun-deployer-access-key-id -w)"
export ALIBABA_CLOUD_ACCESS_KEY_SECRET="$(security find-generic-password -s courseware-space-aliyun-deployer-access-key-secret -w)"
export COURSEWARE_ACCESS_CODE="$(security find-generic-password -s courseware-space-preview-access-code -w)"
export COURSEWARE_TEACHER_STORAGE_KEY='REPLACE_WITH_EXISTING_64_HEX_STORAGE_KEY'
export COURSEWARE_OSS_BUCKET='courseware-space-demo-replace-me'
export COURSEWARE_FEEDBACK_OSS_BUCKET='courseware-space-private-replace-me'

./deploy/build_feedback_package.sh
./deploy/deploy_feedback_only.sh
```

默认命令只输出脱敏 dry-run；核对 `cloud_changes=0`、包 SHA、function、role、policy、环境变量名和 `kimi_env_vars=0` 后，才执行：

```bash
./deploy/deploy_feedback_only.sh --apply
```

两个身份值含义不同：

- `COURSEWARE_ACCESS_CODE` 必须是老师已经收到的原长期链接 fragment，不得轮换；
- `COURSEWARE_TEACHER_STORAGE_KEY` 必须沿用当前 FC 中既有的 64 位 OSS 老师目录键，不得从链接重新计算。

脚本在写入前核验专用 RAM 用户、FC-only 运行角色、精确默认策略版本和唯一策略绑定。它只更新代码包、函数环境与保留并发，不创建、修改或删除 RAM 策略。完整验收见 `docs/deploy/runbook.md`。

## 运行权限

feedback-only 运行策略只允许：

1. 向评价 bucket 的 `feedback/*` 执行 `oss:PutObject`；
2. 读取 `feedback/tasks/*` 与 `feedback/reviews/*`；
3. 在 bucket 资源上以 `oss:Prefix` 条件列举上述两个前缀。

不得授予删除、ACL、其他 bucket、Kimi 或生成服务权限。评价对象采用只追加方式，已有任务和历史不得覆盖。

首批老师任务由 `scripts/build_teacher_review_seed.py` 生成不可变对象。新任务来自既有产品检查点，不因部署自动创建。

## 旧私有 OSS 投递工具

`setup_private_bucket.sh`、`deliver.sh` 与 `private_delivery.py` 是早期固定 OSS 课件路径的历史工具。正式课件现在通过 GitHub Pages 的不可变 revision 发布；不要为普通课件交付重新启用 OSS 长期路径，也不要轮换老师的 Pages 长期链接。

若维护历史 OSS 对象，必须先做本地 manifest 与远端固定前缀对账；只覆盖、不删除残留对象不构成安全重投递。

## 域名切换

备案通过前不绑定自定义域名、不改 DNS。触发后按 `deploy/domain-cutover-runbook.md` 执行；GitHub Pages 入口是否撤下仍由产品负责人另行裁决。
