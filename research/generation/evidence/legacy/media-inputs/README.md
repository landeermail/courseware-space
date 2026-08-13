# 图片 / PDF 输入验收样本

`image-01`～`image-05` 覆盖磁场向里/向外与运动向左/向右的四种方向组合，第五题增加多所求量。SVG 是可审查的题面源文件，PNG 是真实上传输入。

`uncertain-01`～`uncertain-03` 分别缺失关键数值、磁场方向和运动方向，用于验证低置信/缺参不会直接生成。`multi-question.pdf` 在一页中并列两道题，用于验证语义切分。

重新生成 PNG：

```bash
python3 server/evidence/media-inputs/make_samples.py
```

这些图片只用于验证“视觉解析 → 老师确认 → 锁定模板生成”的产品流程，不作为成功率测试答案。预期参数和实际结果由独立验收清单记录。
