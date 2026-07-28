# 阿里云部署与验收 Runbook

## 1. 本地门槛

```bash
python3 scripts/validate_site.py
python3 -m unittest discover -s scripts -p "test_*.py" -v
python3 -m unittest discover -s server/tests -p "test_*.py" -v
python3 server/library_manager.py validate
python3 scripts/validate_generator.py
./deploy/build_package.sh
unzip -tq deploy/dist/courseware-space-fc.zip
```

`auto` 模式在 Apple Silicon 上直接解析 manylinux x86_64 wheels，在 x86_64 主机且 Docker 可用时使用 `python:3.11-slim-bookworm`。如需发布前复核目标容器，可显式执行 `COURSEWARE_BUILD_MODE=docker ./deploy/build_package.sh`；Docker 构建不接收任何 AccessKey。

不得重跑已经锁定结果的 `run_acceptance.py benchmark`、`run_media_acceptance.py` 或 `run_media_edge_acceptance.py`。

## 2. 云端部署

按 `deploy/README.md` 从钥匙串临时注入 key，执行 `deploy/deploy.sh`。每一步都使用精确 `courseware-space-*` 名称；不要改成列表后批量操作。

脚本顺序：

1. 构建内容寻址 ZIP；
2. 创建/核验 private OSS bucket；
3. 上传 private FC code object；
4. 创建任务专属 RAM role 与仅允许 `staging/*` 写入的 policy；
5. 创建/更新 FC function；
6. 创建 HTTP trigger；
7. 设置保留并发 1；
8. 写入本地 `cloud-state.json`。

## 3. 公网验收

先检查：

```bash
curl --fail --silent --show-error "$PUBLIC_URL/api/health"
```

随后必须用真实浏览器完成：

- 桌面：文字、图片、PDF 三种输入；
- 375px：三种输入至少各完成一次；
- 5 道文字题成功、3 道范围外转人工；
- 5 张图片经确认闸生成、3 张不确定图提示补述；
- 1 页 2 题 PDF 能选择其中一题；
- 反向磁场故障注入红→绿；
- 20 题云端基准成功率不少于 60%；
- OSS 产物 URL 可打开并交互，浏览器控制台无本次引入错误。
- 从 GitHub Pages 页面发出的 OPTIONS/POST/GET 请求均返回精确的 `Access-Control-Allow-Origin: https://landeermail.github.io`；其他 Origin 不获得跨域授权。

完整公网套件使用独立、一次性证据文件，不覆盖本地基准：

```bash
python3 server/run_cloud_acceptance.py \
  --base-url https://coursewenerator-zuhffdutvy.cn-hangzhou.fcapp.run
```

脚本会拒绝覆盖既有 `server/evidence/cloud-v2/results.json`。当前限流面向单个老师，完整套件的 POST 数超过 30；如确需从零复验，只能在受控窗口临时调整单客户端限流、保留全局 80 和 FC 并发 1，并在完成后立即恢复并只读核验。不要伪造客户端地址绕过限流。

FC 默认域名会对直接页面导航强制 `Content-Disposition: attachment`，因此禁止把 FC 根路径当页面入口。验收路径固定为：GitHub Pages 加载静态前端 → `fetch` FC JSON API → 打开 OSS 产物 URL。若 JSON `fetch` 也被下载策略或 CORS 阻断，立即停止验收，不得把下载行为冒充页面可用。

## 4. 回滚

只允许用 `deploy/rollback_code.sh` 把函数指向已知 SHA-256 code object。没有销毁脚本；任何删除 bucket、function、role、policy 或对象的动作都必须另行授权。
