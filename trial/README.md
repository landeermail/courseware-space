# 老师试用工具包

- `index.html`：六维打分页，只在浏览器本地生成 JSON。
- `protocol.md`：第一次 60 分钟试用流程。
- `question-template.html`：私有单题页通用模板。
- `build_private_materials.py`：从私有 manifest 和老师 DOCX 提取 PNG 并生成三道本地题页。

## 生成私有题页

私有 manifest 固定放在 `trial/private/questions.json`，完整题干、来源与 DOCX 图片成员名都只写在该文件。`trial/private/.gitignore` 会排除它和生成结果。

```bash
python3 trial/build_private_materials.py \
  --source-docx "/path/to/模拟考试--解析版.docx"
```

生成后从本地服务器访问 `trial/private/questions/<题目 ID>/`。脚本拒绝输出到 `trial/private/` 之外，也会拒绝含“答案/解析/详解”、外部 URL 或脚本的题目内容。

```bash
python3 trial/validate_private_materials.py
python3 -m unittest discover -s trial -p "test_*.py"
```

两台电脑需要通过私有渠道同步 `trial/private/`；不要借助公开 Git 分支或 GitHub Pages 传输老师材料。
