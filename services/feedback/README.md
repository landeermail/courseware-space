# 六维评价与老师工作区

`schema.json` 和 `validate_feedback.py` 定义六维评价的基础业务规则：六个维度必须齐全，失败维必须说明原因，整体打回和 `other` 也必须补充说明。数据不记录老师姓名、学校、联系方式或题目原文。

## 当前线上工作区

老师从原长期题库进入 `reviews/` 查看历史，从课件或题库进入 `feedback/` 评价精确 revision。任务与历史由 `services/feedback/app.py` 从私有 OSS 加载：

- `feedback/tasks/<teacher_key>/<task_id>.json`：不可变评价任务；
- `feedback/reviews/<teacher_key>/<task_id>/<feedback_id>.json`：不可变评价版本。
- `feedback/reviews/<teacher_key>/<task_id>/<disposition_id>.json`：不可变任务处置记录。

状态按精确任务的评价版本和处置记录计算：没有二者为 `pending`，存在评价版本为 `reviewed`，固定表单义务被产品明确撤回且没有评价版本时为 `closed`。修改评价会追加新版本并指向前一版，不覆盖旧证据；处置也不删除任务或伪装成老师评价。q01 v7 的评价不能满足 q01 v8 的任务。浏览器缓存只改善界面，不能决定状态。

新任务由产品检查点决定并通过 `services/feedback/tools/build_teacher_review_seed.py` 生成，不因页面访问、部署或新 revision 自动创建。旧固定表单任务的处置对象由 `services/feedback/tools/build_teacher_review_dispositions.py` 生成；部署者没有私有评价 Bucket 权限时，可在获授权的单次部署中通过 `COURSEWARE_REVIEW_DISPOSITIONS_JSON` 交给受限 FC 运行角色追加，确认写入后立即移除该环境变量。当前原老师长期链接必须保持不变。

## 本地与研究数据

`schema/` 保存当前 schema、校验器与无个人信息样例；`history/` 保存既有校准证据。真实老师反馈默认保存在私有 OSS，不提交公开仓库。`deploy/` 是 feedback-only 包的唯一打包与部署接口，默认部署命令只输出脱敏 dry-run。

如需离线检查：

```bash
python3 services/feedback/schema/validate_feedback.py services/feedback/schema/example.json
python3 -m unittest discover -s services/feedback/tests -p "test_*.py"
services/feedback/deploy/build_package.sh
```

领域决策见 `docs/adr/0009-teacher-review-workspace-on-private-oss.md` 与 `docs/adr/0013-close-retired-teacher-review-tasks-with-dispositions.md`。
