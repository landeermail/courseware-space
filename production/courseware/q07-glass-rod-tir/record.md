# 实心玻璃管中的全反射计数

- question_id: q07-glass-rod-tir
- courseware_id: q07-glass-rod-tir
- lifecycle: production
- workflow_state: closed
- revision_id: 5c8590bd2060
- next_actor: none
- next_action: none
- candidate_path: none
- release_root: site/preview/TNlUdPGF-r2ZDQ4ZDFWYHS8ERlIxaUJT/
- allowed_write_paths: none
- blocked_preflight: 2026-08-20 已重读 BLOCKED.md；本任务不触发临时 Root AccessKey 已清理结论或备案后域名切换
- current_evidence_refs: 本记录；docs/adr/0010-teacher-controlled-interactive-tool.md；docs/adr/0011-default-to-minimal-courseware-research-experiments.md；docs/adr/0013-close-retired-teacher-review-tasks-with-dispositions.md；PROGRESS.md v11；2026-08-20 生产评价 API 核验
- skill_revision: lean-lifecycle-2026-08-20

## Goal and evidence boundary

保留 q07 已发布精确版本和顾问老师的产品反馈，同时结束已经退出当前产品协议的固定六维补填义务。结束旧任务不等于补录老师评价，也不证明精确 revision 已送达、被打开或被接受。

## Current artifact

- 不可变源码：`site/preview/TNlUdPGF-r2ZDQ4ZDFWYHS8ERlIxaUJT/q07-v4-5bb63ec7f581/`。
- manifest revision：`5c8590bd20609630581c97f1e743cd88b8850127f8beabb5d0496467b902b86f`；线上 `index.html` SHA-256：`5bb63ec7f581ee4923aa4b3c5a3c5623ea75f4a6f648597f1840a7350c827ead`。
- 发布与老师长期题库真实入口已经验证；旧记录没有留下该精确 revision 的发送、打开或评价凭证。

## Direct evidence

- ADR 0010 记录顾问老师对 q07 给出明确正面意见，但没有在该处标明意见对应的精确 revision。
- 服务端为 revision `5c8590bd2060` 建立了旧六维评价任务，因此老师题库持续显示待评价。
- 旧生产记录同时写着该精确 revision 尚未发送，和 ADR 0010 的反馈存在版本归属缺口。

## Interpretation

不能把顾问老师的正面意见强行绑定到 `5c8590bd2060`，也没有理由继续要求老师补填已经退出默认协议的表单。最诚实的收口是结束旧任务，同时保留“精确 revision 是否实际体验”未验证。

## Decision and next action

产品负责人于 2026-08-20 授权完整收口。评价服务已部署包 `de110628bf60b7705a8b943917840ee5446a717b9e44cc6b2f5771b55bb3b642`，受限 FC 运行角色已追加处置对象并移除一次性迁移变量；生产 API 返回 q07 为 `closed`。本轮结束，不再要求老师补填固定表单。

## Verified and unverified

- 已验证：物理结论、发布 revision、真实入口、顾问老师对 q07 的正面产品意见及旧状态成因；生产评价 API 返回 q07 `closed`、无伪造评价，迁移环境变量已移除。
- 未验证：正面意见对应的精确 revision；该 revision 的发送、打开与学生效果。

## Token observation and reusable-learning candidates

- 本题历史 Token 未形成可比总量。
- 待跨题复验：当评价协议改变时，应通过明确任务处置结束旧义务，而不是删除历史或要求老师重填。
