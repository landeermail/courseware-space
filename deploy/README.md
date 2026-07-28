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
- 三个 key 只通过环境变量临时注入。

当前演示资源已经创建；实际资源名和最近部署状态只保存在忽略版本控制的 `deploy/dist/cloud-state.json`。历史阻塞与裁决见根目录 `BLOCKED.md`。

## 部署

```bash
export ALIBABA_CLOUD_ACCESS_KEY_ID="$(security find-generic-password -a "$USER" -s courseware-space-aliyun-access-key-id -w)"
export ALIBABA_CLOUD_ACCESS_KEY_SECRET="$(security find-generic-password -a "$USER" -s courseware-space-aliyun-access-key-secret -w)"
export KIMI_API_KEY="$(security find-generic-password -a "$USER" -s courseware-space-kimi -w)"
export ALIYUN_CLI=/absolute/path/to/aliyun
export COURSEWARE_OSS_BUCKET=courseware-space-demo-unique-suffix
# 可省略：默认 auto；发布前兼容性复核可显式设为 docker
export COURSEWARE_BUILD_MODE=auto

./deploy/deploy.sh
```

部署状态写入忽略版本控制的 `deploy/dist/cloud-state.json`。部署脚本不会打印 key；出现错误时也只输出云服务错误码和脱敏资源名。

## 回滚

部署包以 SHA-256 作为 OSS 对象名，旧版本不会被覆盖或删除。将 `cloud-state.json` 或交付记录中的旧 `code_object` 传给：

```bash
export COURSEWARE_FC_CODE_OBJECT=deploy/code/<sha256>.zip
./deploy/rollback_code.sh
```

回滚只更新函数代码指针，不修改环境变量、角色、触发器或 OSS 对象。
