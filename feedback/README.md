# 六维评价与老师工作区

`schema.json` 和 `validate_feedback.py` 定义六维评价的基础业务规则：六个维度必须齐全，失败维必须说明原因，整体打回和 `other` 也必须补充说明。数据不记录老师姓名、学校、联系方式或题目原文。

## 当前线上工作区

老师从原长期题库进入 `reviews/` 查看历史，从课件或题库进入 `feedback/` 评价精确 revision。任务与历史由 `server/feedback_app.py` 从私有 OSS 加载：

- `feedback/tasks/<teacher_key>/<task_id>.json`：不可变评价任务；
- `feedback/reviews/<teacher_key>/<task_id>/<feedback_id>.json`：不可变评价版本。

状态按任务是否存在评价版本计算。修改评价会追加新版本并指向前一版，不覆盖旧证据；q01 v7 的评价不能满足 q01 v8 的任务。浏览器缓存只改善界面，不能决定待评价状态。

新任务由产品检查点决定并通过 `scripts/build_teacher_review_seed.py` 生成，不因页面访问、部署或新 revision 自动创建。当前原老师长期链接必须保持不变。

## 本地与研究数据

仓库中的 `example.json` 仅为无个人信息的格式样例，`calibration-*.json` 与 `review-q01-20260730.json` 是既有校准证据。真实老师反馈默认保存在私有 OSS，不提交公开仓库。

如需离线检查：

```bash
python3 feedback/validate_feedback.py feedback/example.json
python3 -m unittest discover -s feedback -p "test_*.py"
python3 -m unittest server.tests.test_review_workspace server.tests.test_feedback_app
```

领域决策见 `docs/adr/0009-teacher-review-workspace-on-private-oss.md`。
