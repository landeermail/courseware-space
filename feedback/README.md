# 六维反馈数据

`schema.json` 定义单次课件评价的数据格式，`validate_feedback.py` 使用 Python 标准库执行同一组业务校验。反馈只记录匿名会话、评价角色和课件 ID，不记录老师姓名、联系方式或题目原文。

## 导出与落盘

1. 在仓库根目录启动 `python3 -m http.server 8000`。
2. 打开 <http://localhost:8000/trial/>，完成六维评价。
3. 复制 JSON 或下载文件。
4. 需要纳入研究数据时，将文件放到经授权的数据存储位置；不要未经确认把真实老师反馈提交到公开仓库。

仓库中的 `example.json` 仅是无个人信息的格式样例。

## 校验

```bash
python3 feedback/validate_feedback.py feedback/example.json
python3 -m unittest discover -s feedback -p "test_*.py"
```

规则摘要：六个维度必须齐全；`fail` 必须填写该维原因；整体 `reject` 必须选择原因；选择 `other` 必须填写整体备注；不允许 schema 之外的字段。
