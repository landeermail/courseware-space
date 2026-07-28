# 题库区

`catalog.json` 是合格课件目录；`metadata.schema.json` 定义单个课件元数据。现有课件保持原资源路径，通过目录登记进入题库，避免破坏 GitHub Pages 相对路径。

新生成课件必须先写入 `generator/staging/<id>/`，状态为 `pending_review`。老师或维护者确认物理参数后，使用晋升命令复制到 `library/courseware/<id>/` 并登记为 `published`：

```bash
python3 server/library_manager.py promote <id> \
  --reviewer "审核人" \
  --accept-physics
```

晋升不会删除 staging 原件，便于保留生成和审核证据。校验命令：

```bash
python3 server/library_manager.py validate
```
