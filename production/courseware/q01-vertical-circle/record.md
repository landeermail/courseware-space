# 竖直圆环上的双带电小球

- question_id: q01-vertical-circle
- courseware_id: q01-vertical-circle
- revision_id: q01-v8-1c89623d5bf0
- entry_mode: feedback-iteration
- current_stage: teacher-evaluation
- workflow_state: waiting
- next_role: requesting-teacher
- next_action: 等待老师对精确 revision q01-v8-1c89623d5bf0 的新六维评价；收到直接证据后由产品协调者核对 revision 和反馈版本，再回到产品检查点裁决接受、迭代或题库晋升
- question_packet_path: production/courseware/q01-vertical-circle/input/
- candidate_path: production/courseware/q01-vertical-circle/work/candidate/
- evidence_path: production/courseware/q01-vertical-circle/work/evidence/
- release_root: site/preview/TNlUdPGF-r2ZDQ4ZDFWYHS8ERlIxaUJT/
- allowed_write_paths: none
- physics_gate: passed
- physics_review: passed
- teaching_plan: approved
- blueprint_approval: approved
- a0_status: passed
- artifact_manifest_ref: production/courseware/q01-vertical-circle/record.md#artifact-identity-and-a0
- artifact_review_level: A1
- artifact_review_revision_id: q01-v8-1c89623d5bf0
- artifact_review_status: passed
- artifact_review_evidence_ref: production/courseware/q01-vertical-circle/record.md#independent-artifact-review
- teacher_ready_revision: q01-v8-1c89623d5bf0
- delivery_ref: Pages PR 21; merge 1bfab618906106640706ac243f9156d460a34957; deploy run 30993320621; product-owner reported sent 2026-08-05 17:48 CST
- access_path: 原老师长期 GitHub Pages 题库链接，经稳定卡片进入 q01-v8-1c89623d5bf0/；访问 fragment 不写入记录
- outcome: delivered
- promoted_revision_id: none
- decision_owner: product-owner
- approval_ref: q01 blueprint v3.0 approved; q01-v8 A0 and A1 passed; Pages machine gate and product-owner real-entry confirmation passed
- blocked_preflight: 2026-08-13 production 模块路径治理前重新读取 BLOCKED.md；临时 Root AccessKey 云端删除与备案后域名切换均未触发本地迁移，不得宣称凭证已彻底收口
- current_evidence_refs: 本记录；feedback/review-q01-20260730.json 为早期 revision 历史反馈；当前不可变 revision 目录；Pages PR 21 与 deploy run 30993320621
- skill_revision: production-module-paths-2026-08-13

## Question packet and source uncertainty

半径为 `R` 的固定光滑绝缘圆环位于竖直平面内。两个相同带电小球 `a`、`b` 只能沿环移动，初始静止且球间距离为 `R`。外力缓慢推动左球 `a` 到最低点 `c` 后撤去，判断推动阶段的支持力、外力功、势能变化及撤力后的能量守恒。

- 规范题面与原图：`production/courseware/q01-vertical-circle/input/question.md`、`source.png`。
- 已确认勘误：原稿 A 项“b求”按语义更正为“b球”。
- 参考答案 BD 只作对照；原稿对 C 的解释不充分，不覆盖下列独立物理结论。

## Physics truth contract and review

- 推动阶段为准静态约束路径；`b` 的切向平衡与径向方程共同决定位置和支持力，支持力由 `2mg/√3` 单调减至 `mg`。
- 两球—地球—静电相互作用构成能量系统；推动阶段两球总重力势能与电势能均增加，外力做正功。
- 撤力后外力消失，圆环支持力不做功，`K+Ug+Ue` 守恒。
- 独立结论为 B、D；A、C 错。当前可复跑物理参考与 5 项单测位于 `production/courseware/q01-vertical-circle/input/`；历史截图和日志不属于恢复输入。
- 物理未决项：无。不得把探索性电荷缩放数据当作题设条件，也不得画反 `b` 所受支持力方向。

## Approved teaching plan and blueprint

- 现行方案为 blueprint v3.0：动态层显化缓慢推动的耦合变化和撤力后的演化，静态推理层让学习者选择切向/径向、比较关系、选择系统并回到 A–D。
- 规范符号和图式语义 ID 维持图、式、文字和状态一致；自由导航不得依赖点击次数；机器小数与生产术语不得进入学习者主路径。
- 支持桌面与 iPad 横屏 1024×768；手机和 iPad 竖屏只显示转向提示。

## Artifact identity and A0

- 不可变源码目录：`site/preview/TNlUdPGF-r2ZDQ4ZDFWYHS8ERlIxaUJT/q01-v8-1c89623d5bf0/`；公开 URL 仍省略 `site/` 前缀。
- 线上 `index.html` SHA-256：`1c89623d5bf0c1f5e4f1722a1799a2ea9a7b563849ca20d88b0e44585e583e45`。
- A0 覆盖物理参考、静态引用、学习者表面、桌面与 iPad 横屏、自由导航、图式绑定、推动/撤力状态和资源加载；当前 revision 的候选与发布字节已由 Pages 真实入口对账。

## Independent artifact review

- `A1` 对精确 `q01-v8-1c89623d5bf0` 通过；开放 P0/P1 为零。
- 通过项包括证据卡渐进披露、推动时 a/b 耦合、系统问题乱序状态一致，以及桌面与 iPad 横屏主要交互。
- 未检查范围继续是老师对当前 revision 的教学评价、真实学生理解与近迁移、手机和 iPad 竖屏。
- 历史 v7 A2 与 v8 首次 A1 的被替代结论不进入当前放行依据。

## Release, delivery, and feedback

- q01 卡片、课件、相对资源与评价入口的机器 live gate 已通过，产品负责人也曾通过原老师长期链接实际确认。
- 产品负责人于 2026-08-05 报告已发送；该事实只证明发送动作，不证明老师收到、打开、评价、满意或接受。
- `feedback/review-q01-20260730.json` 是更早 revision 的老师反馈，不能满足当前 revision 的评价任务；其“信息要由逻辑串联”等直接证据已用于形成当前方案，但不得冒充 q01-v8 的评价。
- 当前只等待老师对 q01-v8 的新证据；没有新证据时不轮询、不修改课件、不自动晋升题库。
