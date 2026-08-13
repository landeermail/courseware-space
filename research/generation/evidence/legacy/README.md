# 生成平台 MVP 验收证据

## 任务 2：真出活与安全兜底

- `task2/results.json`：5 道范围内题、3 道范围外题及错误参数红→绿记录；
- `task2/manual-requests.jsonl`：3 道范围外题自动进入人工待处理清单；
- `task2/corrupt-manual.jsonl`：负电阻错误参数触发模板校验后的人工兜底记录；
- `generator/generated/task2/`：5 份可直接打开和操作的课件产物。

实际结果：范围内 `5/5` 生成成功，范围外 `3/3` 转人工；5 道范围内题的提取参数与人工预定值逐项一致。

## 任务 3：一次成功率

- `benchmark/results.json`：20 道题的来源、首次状态、结构化参数与产物路径；
- `generator/generated/benchmark/`：20 份首次生成产物；
- `server/fixtures/benchmark-20.json`：冻结前准备的独立题目集。

实际结果：`20/20 = 100%`。每道题的 `attempt` 均为 `1`，且提取参数与人工预定值 `20/20` 一致；基准脚本发现结果文件已存在时会拒绝再次运行。

浏览器抽查入口：`generator/generated/index.html`。
