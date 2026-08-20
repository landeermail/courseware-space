# 老师反馈工作区

新老师试用任务默认接收一段自由反馈，不要求按维度打分。`schema.json` 和 `validate_feedback.py` 继续定义旧六维评价的兼容规则：六个维度必须齐全，失败维必须说明原因，整体打回和 `other` 也必须补充说明。两种方式都不记录老师姓名、学校、联系方式或题目原文。

## 当前线上工作区

老师从原长期题库进入 `reviews/` 查看历史，从题库进入 `feedback/` 反馈精确 revision。任务与历史由 `services/feedback/app.py` 从私有 OSS 加载：

- `feedback/tasks/<teacher_key>/<task_id>.json`：不可变反馈任务；`feedback_mode` 缺省为旧 `structured`，新任务默认显式使用 `freeform`；
- `feedback/reviews/<teacher_key>/<task_id>/<feedback_id>.json`：不可变反馈版本；六维历史为 schema v2，自由反馈为 schema v3；
- `feedback/reviews/<teacher_key>/<task_id>/<disposition_id>.json`：不可变任务处置记录。

状态按精确任务的反馈版本和处置记录计算：没有二者为 `pending`，存在反馈版本为 `reviewed`，旧义务被产品明确撤回且没有反馈版本时为 `closed`。界面分别显示“等待反馈”“已反馈”“已结束”。补充反馈会追加新版本并指向前一版，不覆盖旧证据；经产品负责人转述的反馈必须保存来源引用，不能冒充老师在线提交。q01 v7 的评价不能满足 q01 v8 的任务。浏览器缓存只改善界面，不能决定状态。

新任务由产品检查点决定，不因页面访问、部署或新 revision 自动创建。首批旧任务由 `services/feedback/tools/build_teacher_review_seed.py` 生成，旧固定表单处置由 `services/feedback/tools/build_teacher_review_dispositions.py` 生成；474 的自由反馈任务和已有转述反馈由 `services/feedback/tools/build_q474_free_feedback_update.py` 生成。所有生成器都只产出本地追加对象，不直接写云。获授权部署时可把生成的 `review-updates.json` 压缩为 `COURSEWARE_REVIEW_UPDATES_JSON`，由 FC 运行角色幂等追加；确认接口状态后必须再次部署并移除该一次性变量。当前原老师长期链接必须保持不变。

## 本地与研究数据

`schema/` 保存当前 schema、校验器与无个人信息样例；`history/` 保存既有校准证据。真实老师反馈默认保存在私有 OSS，不提交公开仓库。`deploy/` 是 feedback-only 包的唯一打包与部署接口，默认部署命令只输出脱敏 dry-run。

如需离线检查：

```bash
python3 services/feedback/schema/validate_feedback.py services/feedback/schema/example.json
python3 -m unittest discover -s services/feedback/tests -p "test_*.py"
services/feedback/deploy/build_package.sh
```

领域决策见 `docs/adr/0009-teacher-review-workspace-on-private-oss.md`、`docs/adr/0013-close-retired-teacher-review-tasks-with-dispositions.md` 与 `docs/adr/0014-default-to-freeform-teacher-feedback.md`。
