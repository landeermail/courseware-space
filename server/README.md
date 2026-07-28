# 本地课件生成服务

该服务使用 Python 标准库同时提供仓库静态文件和生成 API。生成请求进入内存线程池，Kimi Code 只负责把题目转换为受限参数；物理公式、方向与页面代码均由锁定模板提供。

## 启动

API Key 推荐保存在 macOS 钥匙串，服务启动时临时注入环境变量：

```bash
KIMI_API_KEY="$(security find-generic-password -a "$USER" -s courseware-space-kimi -w)" \
  python3 server/app.py
```

然后访问 <http://localhost:8000/generator/>。

默认运行数据保存在 `/tmp/courseware-space-generator/`：

- `generated/<job-id>/index.html`：生成结果；
- `manual-requests.jsonl`：自动兜底和老师提交的人工请求事件。

可以通过 `COURSEWARE_RUNTIME_DIR` 改变运行目录。API Key 不得写入前端、运行结果、日志或仓库。

## API

- `GET /api/health`：服务和 provider 配置状态；
- `POST /api/generate`：提交 `{ "question": "..." }`，立即返回异步任务；
- `GET /api/jobs/<job-id>`：查询生成状态；
- `POST /api/manual-requests`：为已转人工的任务补充称呼和联系方式；
- `GET /generated/<job-id>/`：打开生成页面。

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

## 部署边界

GitHub Pages 只能发布静态前端和已生成课件，不能运行该 Python API。当前 MVP 面向本机现场演示；公开生成服务需要另行确定后端托管方案，并在商业上线前迁移到 Kimi 开放平台或取得相应许可。
