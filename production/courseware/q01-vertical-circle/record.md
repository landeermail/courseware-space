# 竖直圆环上的双带电小球

- question_id: q01-vertical-circle
- courseware_id: q01-vertical-circle
- lifecycle: production
- workflow_state: closed
- revision_id: q01-v8-1c89623d5bf0
- next_actor: none
- next_action: none
- candidate_path: none
- release_root: site/preview/TNlUdPGF-r2ZDQ4ZDFWYHS8ERlIxaUJT/
- allowed_write_paths: none
- blocked_preflight: 2026-08-20 已重读 BLOCKED.md；本任务不触发临时 Root AccessKey 已清理结论或备案后域名切换
- current_evidence_refs: 本记录；docs/adr/0010-teacher-controlled-interactive-tool.md；docs/adr/0011-default-to-minimal-courseware-research-experiments.md；docs/adr/0013-close-retired-teacher-review-tasks-with-dispositions.md；PROGRESS.md v11；services/feedback/history/review-q01-20260730.json；2026-08-20 生产评价 API 核验
- skill_revision: lean-lifecycle-2026-08-20

## Goal and evidence boundary

保留 q01 已发布精确版本及老师反馈，同时结束已经退出当前产品协议的固定六维补填义务。结束旧任务不等于老师提交了 q01 v8 的结构化评价，也不自动证明接受、学生学习或题库晋升。

## Current artifact

- 不可变源码：`site/preview/TNlUdPGF-r2ZDQ4ZDFWYHS8ERlIxaUJT/q01-v8-1c89623d5bf0/`。
- 线上 `index.html` SHA-256：`1c89623d5bf0c1f5e4f1722a1799a2ea9a7b563849ca20d88b0e44585e583e45`。
- q01 v8 已发布并于 2026-08-05 由产品负责人报告发送；原老师长期链接保持不变。

## Direct evidence

- 2026-08-13，产品负责人记录老师已实际打开 q01 v8，并反馈“远远超出预期”，需要时间认真思考建议。
- ADR 0010 的产品方向讨论记录老师认为 q01 完全吃透题目、整体很好，但“处处都很重、没有突出”；该记录没有再次标明精确 revision，不补推版本归属。
- `services/feedback/history/review-q01-20260730.json` 属于更早 q01 v7，不能冒充 q01 v8 的评价。

## Interpretation

老师已经提供了有价值的自由反馈；继续把 q01 v8 显示为必须补交六维表单，与 ADR 0011 的当前评价方式冲突。现有证据足以结束旧表单义务，但不足以补写一份结构化评价或证明学生效果。

## Decision and next action

产品负责人于 2026-08-20 授权完整收口。评价服务已部署包 `de110628bf60b7705a8b943917840ee5446a717b9e44cc6b2f5771b55bb3b642`，受限 FC 运行角色已追加处置对象并移除一次性迁移变量；生产 API 返回 q01 v8 为 `closed`。本轮结束，不再要求老师补填固定表单。

## Verified and unverified

- 已验证：物理结论、发布 revision、真实入口、既有老师原话、旧状态成因；生产评价 API 返回 q01 v8 `closed`、无伪造评价，迁移环境变量已移除。
- 未验证：学生学习与迁移；ADR 0010 后续意见是否专指 q01 v8。

## Token observation and reusable-learning candidates

- 本题历史 Token 未形成可比总量。
- 待跨题复验：自由反馈应在产品记录中直接收口，不再等待老师把同一意见重填为固定表单。
