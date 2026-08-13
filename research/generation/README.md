# 本地课件生成研发

本目录是生成研发的唯一职责模块：`app.py` 是本地 HTTP 入口，`runtime/` 保存 Kimi、生成、媒体和运行存储实现，`harness/`、`templates/`、`library/` 与必要证据均在本模块内。当前公网 feedback-only 服务由 `services/feedback/` 独立拥有。

不要把本地生成能力等同于当前线上产品能力。

## 本地生成研发

`app.py` 使用标准库提供仓库静态文件和生成 API。Kimi Code 只把题目转换为受限参数，物理公式、方向和页面代码由锁定模板与 harness 约束。

```bash
KIMI_API_KEY="$(security find-generic-password -s courseware-space-kimi -w)" \
COURSEWARE_ACCESS_CODE="$(security find-generic-password -s courseware-space-preview-access-code -w)" \
  python3 research/generation/app.py
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

generation 不拥有 `/api/feedback`、老师评价任务或 feedback 部署入口；这些只属于 `services/feedback/`。旧公网 generation 部署脚本已退出当前树，由 Git 历史保留，不得用本地研发入口覆盖当前 feedback-only FC。

## 验证

```bash
python3 -m unittest discover -s research/generation/harness/tests -p "test_*.py"
python3 -m unittest discover -s research/generation/tests -p "test_*.py"
python3 research/generation/validate.py
```

完整历史模型尝试链由 Git 历史承担；当前 `harness/evidence/` 只保留正式验收实际消费的生成物和摘要，`evidence/legacy/` 保存旧模板管线校验仍需的最小证据与媒体夹具。两个证据目录通过 `.ignore` 退出普通 `rg` 搜索，正式验证器仍直接读取。
