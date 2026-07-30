# 阿里云演示部署

本目录提供可复跑的 FC 3.0 + OSS 部署。部署使用 FC `custom.debian12` Web 函数承载现有 Python HTTP 服务；生成结果写入 private bucket 的 `staging/<job-id>/`，仅产物对象设置 `public-read`；FC 通过任务专属 RAM role 获取临时 STS 凭证。

网页入口仍由 GitHub Pages 托管。`generator/index.html` 在 Pages 上以跨域 `fetch` 调用 FC JSON API，再展示 OSS 产物；不要直接导航到 FC 默认域名。

## 资源边界

- OSS bucket：`courseware-space-*`；
- FC function / HTTP trigger：`courseware-space-*`；
- RAM role / custom policy：`courseware-space-*`；
- 脚本没有删除、销毁、改支付或修改账号既有资源的命令；
- 发现同名既有 bucket 不是 private，或既有 bucket 阻止对象 public-read 时，脚本停止而不是改权限。

## 前置条件

- 阿里云 CLI 3.3.0 或更高版本，并安装 `sts`、`fc`、`ram` 插件；
- Python 3、`jq`、`zip`；
- Docker 可选；`auto` 模式在 Apple Silicon 上默认使用 manylinux x86_64 wheels，避免慢速架构仿真；x86_64 主机有 Docker 时使用目标 Linux 容器；
- 阿里云 OSS 服务已启用；
- AccessKey、Kimi key 与预览访问码只通过环境变量临时注入；访问码推荐保存于 macOS 钥匙串服务 `courseware-space-preview-access-code`。

当前演示资源已经创建；实际资源名和最近部署状态只保存在忽略版本控制的 `deploy/dist/cloud-state.json`。历史阻塞与裁决见根目录 `BLOCKED.md`。

## 部署

```bash
export ALIBABA_CLOUD_ACCESS_KEY_ID="$(security find-generic-password -a "$USER" -s courseware-space-aliyun-access-key-id -w)"
export ALIBABA_CLOUD_ACCESS_KEY_SECRET="$(security find-generic-password -a "$USER" -s courseware-space-aliyun-access-key-secret -w)"
export KIMI_API_KEY="$(security find-generic-password -a "$USER" -s courseware-space-kimi -w)"
export COURSEWARE_ACCESS_CODE="$(security find-generic-password -a "$USER" -s courseware-space-preview-access-code -w)"
export ALIYUN_CLI=/absolute/path/to/aliyun
export COURSEWARE_OSS_BUCKET=courseware-space-demo-unique-suffix
export COURSEWARE_FEEDBACK_OSS_BUCKET=courseware-space-private-unique-suffix
# 可省略：默认 auto；发布前兼容性复核可显式设为 docker
export COURSEWARE_BUILD_MODE=auto

./deploy/deploy.sh
```

本机钥匙串服务名采用仓库约定时，也可以直接运行 `./deploy/deploy_from_keychain.sh`。脚本只把访问码注入 FC 环境变量，不打印其值；运行角色只允许写 demo bucket 的 `staging/*` 与 private bucket 的 `feedback/*`。

部署状态写入忽略版本控制的 `deploy/dist/cloud-state.json`。部署脚本不会打印 key；出现错误时也只输出云服务错误码和脱敏资源名。

## 回滚

部署包以 SHA-256 作为 OSS 对象名，旧版本不会被覆盖或删除。将 `cloud-state.json` 或交付记录中的旧 `code_object` 传给：

```bash
export COURSEWARE_FC_CODE_OBJECT=deploy/code/<sha256>.zip
./deploy/rollback_code.sh
```

回滚只更新函数代码指针，不修改环境变量、角色、触发器或 OSS 对象。

## 私有课件长期链接

内部试题课件使用独立的 `courseware-space-private-10794778` bucket，与生成器 demo bucket、FC 和 RAM 完全分离。bucket ACL 保持 `private`；Bucket Policy 只允许匿名读取 `private/*` 对象，并显式拒绝 bucket 和前缀列举。完整链接包含 48 位密码学随机路径，不进入 Git。

首次创建或复核 bucket：

```bash
./deploy/setup_private_bucket.sh
```

交付一个课件只需一行：

```bash
./deploy/deliver.sh trial/private/courseware/q01-vertical-circle
```

同一课件默认复用首次随机路径，以保持老师手中的链接长期稳定。映射和历次交付摘要写入被忽略的 `trial/private/deliveries.json`。如果链接泄露，使用 `--rotate`：脚本先上传到新随机路径，成功后删除旧前缀并停用旧记录。

```bash
./deploy/deliver.sh --rotate trial/private/courseware/q01-vertical-circle
```

脚本只接受 `trial/private/courseware/` 下的目录，只允许操作固定 private bucket 和杭州区域。AccessKey 每次从 macOS 钥匙串读取，只注入临时进程；SDK 安装在系统临时目录，不写入仓库。不要把输出链接或 `deliveries.json` 提交到公开仓库。
