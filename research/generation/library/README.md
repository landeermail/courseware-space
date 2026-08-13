# 题库区

`catalog.json` 是当前 generation 晋升区的合格课件目录；`metadata.schema.json` 定义单个课件元数据。既有公开课件由 `site/` 独立拥有，不重复登记为 generation 当前产物。迁移前旧 catalog 保存在 `history/catalog-2026-07-28.json`，不参与默认校验。

新生成课件必须先写入 `generator/staging/<id>/`，状态为 `pending_review`。老师或维护者确认物理参数后，使用晋升命令复制到 `library/courseware/<id>/` 并登记为 `published`：

```bash
python3 research/generation/runtime/library_manager.py promote <id> \
  --reviewer "审核人" \
  --accept-physics
```

晋升不会删除 staging 原件，便于保留生成和审核证据。校验命令：

```bash
python3 research/generation/runtime/library_manager.py validate
```
