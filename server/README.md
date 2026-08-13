# 服务端组件

本目录包含两个用途不同的 Python 服务：

- `app.py`：本地生成研发服务，可调用 Kimi Code；
- `feedback_app.py`：当前公网 FC 的 feedback-only 服务，不包含模型客户端或生成路由。

不要把本地生成能力等同于当前线上产品能力。

## 本地生成研发

`app.py` 使用标准库提供仓库静态文件和生成 API。Kimi Code 只把题目转换为受限参数，物理公式、方向和页面代码由锁定模板与 harness 约束。

```bash
KIMI_API_KEY="$(security find-generic-password -s courseware-space-kimi -w)" \
COURSEWARE_ACCESS_CODE="$(security find-generic-password -s courseware-space-preview-access-code -w)" \
  python3 server/app.py
```

打开 <http://localhost:8000/generator/>。主要接口为：

- `GET /api/health`；
- `POST /api/generate`；
- `POST /api/media/parse` 与 `POST /api/media/confirm`；
- `GET /api/jobs/<job-id>`；
- `POST /api/manual-requests`；
- `GET /generated/<job-id>/`。

图片最大 8 MB，PDF 最大 20 MB、6 页。解析置信不足、模板范围外或关键参数缺失时转补述或人工，不直接生成。默认运行数据在 `/tmp/courseware-space-generator/`，可用 `COURSEWARE_RUNTIME_DIR` 改变；key 不得写入前端、日志、运行结果或仓库。

真实 Kimi 验收会消耗额度，且锁定证据脚本会拒绝覆盖已有结果。只有明确需要重新建立生成证据时才运行 `run_acceptance.py`、`run_media_acceptance.py` 或 `run_media_edge_acceptance.py`。

## 当前公网评价服务

`feedback_app.py` 是独立入口：

- `GET /api/health`：公开健康检查；
- `POST /api/feedback`：保留的受凭证保护六维反馈入口；
- `GET /api/reviews`：读取该老师的全部任务与历史；
- `GET /api/reviews?courseware_id=<id>`：读取某课件最新任务；
- `POST /api/reviews/<task_id>`：为精确 revision 追加新评价版本；
- 其他接口，包括 `/api/generate`、媒体、任务和产物路由：404。

当前云端必须设置：

- `COURSEWARE_CLOUD_MODE=1`；
- `COURSEWARE_ACCESS_CODE`：老师原长期链接的 48 位字母数字凭证；
- `COURSEWARE_TEACHER_STORAGE_KEY`：既有 OSS 老师目录的 64 位 SHA-256 键；
- `COURSEWARE_FEEDBACK_OSS_BUCKET`、OSS region/endpoint；
- 可选的 `COURSEWARE_CORS_ORIGINS` 与限流变量。

老师凭证与存储键不是同一值；部署不得轮换原链接，也不得用新链接重新推导存储键。评价状态和历史由服务端不可变对象计算，浏览器 `localStorage` 不是事实源。

本地可直接运行：

```bash
COURSEWARE_ACCESS_CODE=0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKL \
COURSEWARE_TEACHER_STORAGE_KEY=0000000000000000000000000000000000000000000000000000000000000000 \
  python3 server/feedback_app.py
```

## 验证

```bash
python3 -m unittest discover -s server/tests -p "test_*.py"
python3 -m unittest deploy/test_feedback_only.py deploy/test_private_delivery.py
python3 scripts/validate_generator.py
```

前两项覆盖当前 feedback-only 与评价工作区；最后一项只验证仍保留的本地生成器静态边界。生产部署与真实入口门禁见 `docs/deploy/runbook.md`。
