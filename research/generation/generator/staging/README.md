# 生成待验收区

每个候选课件使用独立目录：

```text
generator/staging/<id>/
├── index.html
└── metadata.json
```

`metadata.json` 必须符合 `library/metadata.schema.json`，包含非空 `owner`，且初始 `status` 为 `pending_review`。未经后端记录老师确认或人工审核，不得进入题库。
