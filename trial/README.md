# 老师试用工具包

本目录保留本地校准工具和生产候选。当前正式单题生产以 `$build-physics-courseware` 与 `production/courseware/<courseware_id>/record.md` 为准；练习题可以公开，不能再把本协议中的“私有”理解为试题保密要求。

- `index.html`：六维打分页，只在浏览器本地生成 JSON。
- `protocol.md`：第一次 60 分钟试用流程。
- `question-template.html`：早期本地单题页通用模板。
- `build_private_materials.py`：从本地 manifest 和老师 DOCX 提取 PNG 并生成三道本地题页。

## 生成本地题页

本地 manifest 固定放在 `trial/private/questions.json`，完整题干、来源与 DOCX 图片成员名都只写在该文件。`trial/private/.gitignore` 会排除它和生成结果。这里的忽略规则用于避免误提交工作材料，不代表这些练习题具有考试保密属性。

```bash
python3 trial/build_private_materials.py \
  --source-docx "/path/to/模拟考试--解析版.docx"
```

生成后从本地服务器访问 `trial/private/questions/<题目 ID>/`。脚本拒绝输出到 `trial/private/` 之外，也会拒绝含“答案/解析/详解”、外部 URL 或脚本的题目内容。

```bash
python3 trial/validate_private_materials.py
python3 -m unittest discover -s trial -p "test_*.py"
```

不要提交未经整理的老师文件、路径或个人信息；正式发布只发布产品检查点批准的精确 revision。
