# 实心玻璃管中的全反射计数

- question_id: q07-glass-rod-tir
- courseware_id: q07-glass-rod-tir
- revision_id: 5c8590bd2060
- entry_mode: resume
- current_stage: release
- workflow_state: waiting
- next_role: product-owner
- next_action: 等待产品负责人决定是否把原老师长期题库链接发送给老师；只有实际发送后才记录 delivery_ref 并把 outcome 改为 delivered，未经授权不联系老师
- question_packet_path: trial/private/questions/q07-glass-rod-tir/
- candidate_path: trial/private/courseware/q07-glass-rod-tir/
- evidence_path: trial/private/development/q07-glass-rod-tir/
- release_root: preview/TNlUdPGF-r2ZDQ4ZDFWYHS8ERlIxaUJT/
- allowed_write_paths: none
- physics_gate: passed
- physics_review: passed
- teaching_plan: approved
- blueprint_approval: approved
- a0_status: passed
- artifact_manifest_ref: trial/private/courseware/q07-glass-rod-tir/manifest.json
- artifact_review_level: A1
- artifact_review_revision_id: 5c8590bd2060
- artifact_review_status: passed
- artifact_review_evidence_ref: production/courseware/q07-glass-rod-tir/record.md#independent-artifact-review
- teacher_ready_revision: 5c8590bd2060
- delivery_ref: none
- access_path: 原老师长期 GitHub Pages 题库链接，经稳定卡片进入 q07-v4-5bb63ec7f581/；访问 fragment 不写入记录
- outcome: pending
- promoted_revision_id: none
- decision_owner: product-owner
- approval_ref: q07-tir-count-plan-v1 and blueprint v3 approved; release adaptation 5c8590bd2060 A0/A1 passed; PR 22 Pages and product-owner real-entry confirmation passed
- blocked_preflight: 2026-08-13 第二批状态迁移前重新读取 BLOCKED.md；临时 Root AccessKey 删除与备案后域名切换均未触发本地迁移，联系老师仍需单独产品负责人决定
- current_evidence_refs: 本记录；规范题包；q07 blueprint v3；candidate manifest 5c8590bd2060；A1-q07-5c8590bd2060-2026-08-12；Pages PR 22 与 deploy run 31588393867
- skill_revision: local-production-path-migration-2026-08-13

## Question packet and source uncertainty

实心玻璃管长 40 cm、宽 4 cm，折射率为 `2/√3`，光从左端正中心射入，求光最多可以在管中反射多少次。

- 规范转写：`trial/private/questions/q07-glass-rod-tir/question.md`。
- 原图：`trial/private/questions/q07-glass-rod-tir/source.png`，SHA-256 `589ce078908d72efaee5f9ee031e3efc11a449ddf2be39ba7d44d68602979ae1`。
- 不从示意图斜率读取角度；入口折射可实现性是正式模型的一部分。

## Physics truth contract and review

- 玻璃内轴向角为 `θ`，侧壁入射角为 `α=90°−θ`，临界角 `C=60°`；严格全反射要求 `θ<30°`。
- 反射点位置 `x_k=(4k−2)/tanθ`；第 6 次存在 `28.81°<θ<30°` 的可行开区间，第 7 次要求的角度与全反射条件冲突，最大值为 6。
- 空气入射角与管内角通过 Snell 关系联立，不把不可实现的管内方向作为自由输入。
- 独立物理复核 `physics-review-q07-2026-08-07` 通过；未决物理项为无。

## Approved teaching plan and blueprint

- 现行 blueprint v3 将学习路径压缩为读原题、找边界、拆开步长、判定上限；主操控是真实空气入射方向。
- 学习者通过跨越 `29.9° → 30.0° → 30.1°` 观察严格全反射边界，再把折叠光路转换为首段 2 cm、周期段 4 cm 和 `x_k`。
- 图、式、文字、角度、反射点与计数只消费 `model.js` 的同一输出。
- 支持桌面与 iPad 横屏 1024×768；手机、竖屏、真实 iPad 手感和老师教学认可不在内部放行范围。

## Artifact identity and A0

- candidate manifest：`trial/private/courseware/q07-glass-rod-tir/manifest.json`，完整 SHA-256 `5c8590bd20609630581c97f1e743cd88b8850127f8beabb5d0496467b902b86f`。
- 不可变目录：`preview/TNlUdPGF-r2ZDQ4ZDFWYHS8ERlIxaUJT/q07-v4-5bb63ec7f581/`；线上 `index.html` SHA-256 `5bb63ec7f581ee4923aa4b3c5a3c5623ea75f4a6f648597f1840a7350c827ead`。
- 当前 revision 是基于已通过 A2 的 `b308c05e69ac` 做发布适配窄修，只增加正式导航、隐私 meta 和版本信号；19 个 payload 已重算一致。
- A0 覆盖模型 92/92、站点和学习者表面、桌面与 iPad 横屏、导航、一个真实滑条拖动、控制台和资源加载。

## Independent artifact review

- `A1` 对精确 `5c8590bd2060` 通过，4 个 rendered states 内无开放 P0/P1。
- 两条生产导航、URL 不含访问码、版本身份、桌面滑条锚点及双视口不遮挡均通过。
- 未检查范围为完整临界矩阵、全部场景、真实 iPad 触控、手机/竖屏、老师认可和真实学习效果；这些不由 A1 冒充通过。

## Product checkpoint and immutable release

- 产品负责人批准 `5c8590bd2060` teacher-ready，并授权发布；PR 22 合并提交 `33c2dfbe23a35ec0bfda4106636f7c8299dbb894`，Pages run `31588393867` 成功。
- 真实入口机器门禁五项及线上 manifest 19/19 对账通过；产品负责人于 2026-08-12 从长期题库实际确认卡片、课件、返回题库和去评价路径。
- 发布与入口确认不等于已经发送老师。当前没有发送、送达、打开、评价或接受证据，因此 `outcome` 保持 `pending`。

## Current waiting boundary

- 下一步只需要产品负责人决定是否发送原长期题库链接；发送动作需在执行前重新读取 `BLOCKED.md`。
- 若发送，记录脱敏 `delivery_ref` 并进入 `teacher-evaluation`；不得在记录中写入老师链接 fragment 或访问码。
- 没有新授权时不重复部署、不创建新 revision、不修改评价服务或老师凭证。
