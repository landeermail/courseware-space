# 本地课件生成服务

该服务使用 Python 标准库同时提供仓库静态文件和生成 API。生成请求进入内存线程池，Kimi Code 只负责把题目转换为受限参数；物理公式、方向与页面代码均由锁定模板提供。

## 启动

API Key 推荐保存在 macOS 钥匙串，服务启动时临时注入环境变量：

```bash
KIMI_API_KEY="$(security find-generic-password -a "$USER" -s courseware-space-kimi -w)" \
  python3 server/app.py
```

然后访问 <http://localhost:8000/generator/>。

图片/PDF 与文字输入都位于 <http://localhost:8000/generator/>；`/generator/media/` 只保留为开发期独立确认台。视觉模型的输出只会创建待确认记录；老师核对或修正全部关键参数并显式勾选后，后端才签发一次性确认令牌并创建生成任务。

默认运行数据保存在 `/tmp/courseware-space-generator/`：

- `generated/<job-id>/index.html`：生成结果；
- `manual-requests.jsonl`：自动兜底和老师提交的人工请求事件。

可以通过 `COURSEWARE_RUNTIME_DIR` 改变运行目录。API Key 不得写入前端、运行结果、日志或仓库。

## API

- `GET /api/health`：服务和 provider 配置状态；
- `POST /api/generate`：提交 `{ "question": "..." }`，立即返回异步任务；
- `POST /api/media/parse`：提交图片/PDF 的文件名、MIME 与 Base64 内容，返回逐题结构化解析；
- `POST /api/media/confirm`：提交老师确认后的题意、B/L/v/R、磁场/运动/电流方向与所求量；未经服务端解析记录和显式确认会被拒绝；
- `GET /api/jobs/<job-id>`：查询生成状态；
- `POST /api/manual-requests`：为已转人工的任务补充称呼和联系方式；
- `GET /generated/<job-id>/`：打开生成页面。

图片最大 8 MB，PDF 最大 20 MB、6 页。PDF 使用 `pdfinfo` + `pdftoppm` 逐页转成图片，每页要求视觉模型返回 `questions[]`，因此一页多题可以作为多条候选供老师选择。这是当前最简单且可审查的切分方案：不尝试不可靠的自动坐标裁图，也不让模型直接读取整份 PDF。无法解析、置信不足、模板范围外或关键参数缺失时返回补述/人工提示，不会直接生成。

## 验证

```bash
python3 -m unittest discover -s server/tests -p "test_*.py" -v
python3 scripts/validate_generator.py
```

真实验收会消耗 Kimi Code 额度，任务 3 基准为保护“一次成功率”证据，存在结果文件时会拒绝重复运行：

```bash
KIMI_API_KEY="$(security find-generic-password -a "$USER" -s courseware-space-kimi -w)" \
  python3 server/run_acceptance.py task2

KIMI_API_KEY="$(security find-generic-password -a "$USER" -s courseware-space-kimi -w)" \
  python3 server/run_acceptance.py benchmark
```

图片/PDF 验收同样会消耗 Kimi Code 额度，并在结果存在时拒绝重跑：

```bash
KIMI_API_KEY="$(security find-generic-password -a "$USER" -s courseware-space-kimi -w)" \
  python3 server/run_media_acceptance.py

KIMI_API_KEY="$(security find-generic-password -a "$USER" -s courseware-space-kimi -w)" \
  python3 server/run_media_edge_acceptance.py
```

云端一次性回归使用 `server/run_cloud_acceptance.py --base-url <FC URL>`，结果写入 `server/evidence/cloud-v2/results.json`。它会真实验证 5+3 道文字题、20 题基准、5+3 张图片、PDF 多题和确认闸红→绿，并逐个打开 OSS 产物；证据存在时同样拒绝重跑。

## 部署边界

GitHub Pages 只发布静态前端；公开生成 API 运行在阿里云 FC，产物写入 OSS。Pages 前端只向配置的 FC 地址发送 JSON `fetch`，服务端以精确 Origin 白名单和限流保护演示接口。该匿名接口不等于生产鉴权，生产化前仍需身份系统、持久化任务状态与持久化限流。
