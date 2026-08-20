# Feedback-only 部署与验收 Runbook

本 Runbook 只用于当前公网评价服务。生成研发位于 `research/generation/`，不提供公网部署入口；旧生成云部署工具仅由 Git 历史保留，不得把含 Kimi key 的研发运行时重新覆盖到生产 FC。

## 1. 写入前检查

1. 读取根目录 `BLOCKED.md`，列出本次触发项；
2. 确认获得部署授权；
3. 使用最新 `main` 的隔离分支或 worktree；
4. 确认老师原长期链接不变，`COURSEWARE_TEACHER_STORAGE_KEY` 沿用当前 FC 的既有值，不从老师链接重新计算。

## 2. 本地门槛

```bash
python3 -m unittest discover -s services/feedback/tests -p "test_*.py"
python3 scripts/validate_site.py
./services/feedback/deploy/build_package.sh
unzip -tq services/feedback/dist/courseware-space-feedback-fc.zip
```

构建脚本只复制白名单服务文件与 OSS SDK；ZIP 中出现 Kimi、生成器、媒体或模板引用会失败。Apple Silicon 默认解析 manylinux x86_64 wheels，不要求 Docker。

## 3. 环境变量

```bash
export ALIYUN_CLI="$HOME/.local/bin/aliyun"
export ALIBABA_CLOUD_ACCESS_KEY_ID="$(security find-generic-password -s courseware-space-aliyun-deployer-access-key-id -w)"
export ALIBABA_CLOUD_ACCESS_KEY_SECRET="$(security find-generic-password -s courseware-space-aliyun-deployer-access-key-secret -w)"
export COURSEWARE_ACCESS_CODE="$(security find-generic-password -s courseware-space-preview-access-code -w)"
export COURSEWARE_FEEDBACK_OSS_BUCKET='courseware-space-private-replace-me'
export COURSEWARE_OSS_BUCKET='courseware-space-demo-replace-me'
export COURSEWARE_TEACHER_STORAGE_KEY='REPLACE_WITH_EXISTING_64_HEX_STORAGE_KEY'
```

`COURSEWARE_ACCESS_CODE` 必须与老师已经持有的原链接完全一致。`COURSEWARE_TEACHER_STORAGE_KEY` 只用于定位已有 OSS 任务与历史；部署前从当前受控生产配置读取并在同一临时 shell 注入，不打印、不提交、不重新生成。两者混淆会导致老师原链接失效或历史不可见。

如需结束旧评价任务，先用现有 `COURSEWARE_TEACHER_STORAGE_KEY` 生成处置对象，再把对象数组仅在一次部署中注入 `COURSEWARE_REVIEW_DISPOSITIONS_JSON`。函数启动后会追加或核对同字节对象；确认接口状态后再次部署并移除该变量。不要为此扩大部署用户的私有 OSS 权限。

如需追加新自由反馈任务或经确认的转述反馈，先用对应有界生成器产出 `review-updates.json`，再把对象数组仅在一次部署中注入 `COURSEWARE_REVIEW_UPDATES_JSON`。函数启动后会逐对象追加或核对同字节内容；确认状态后再次部署并移除该变量。该通道只接受精确绑定 revision 的自由反馈任务和带来源的反馈记录。

## 4. 部署

先执行脱敏 dry-run：

```bash
./services/feedback/deploy/deploy.sh
```

核对包 SHA、指定 function/role/policy、环境变量名、`kimi_env_vars=0` 和 `cloud_changes=0`。确认后才执行：

```bash
./services/feedback/deploy/deploy.sh --apply
```

脚本在任何写入前拒绝 root 身份，并核验运行 role 的 FC-only 信任、精确默认策略版本和唯一策略绑定；随后上传内容寻址 ZIP、原位更新 FC 并重申保留并发 1。它不创建或修改 RAM 策略。

## 5. 生产门禁

所有检查均为只读，不提交老师评价：

- `GET /api/health`：200，`mode=feedback-only`、`feedback_store=oss`；
- `POST /api/generate`：404；
- 老师原凭证请求 `GET /api/reviews`：200；
- 错凭证：403；
- q01 v7 为已评价；写入 ADR 0013 的处置对象后，q01 v8 与 q07 为已结束且没有伪造评价历史；
- Pages 题库、`reviews/`、`feedback/` 和精确课件 revision 均为 200；
- 全新浏览器打开老师原完整链接，fragment 被清除且显示正确的等待反馈数量；没有活动任务时首页不显示空待办区域；
- 匿名 OSS 列举仍为 403。

不得只分别验证 Pages 200 和 API 200；必须证明浏览器从 Pages 带原 fragment 跨域读取生产 API 成功。

## 6. 回滚

代码包按 SHA-256 存放在 OSS。回滚只允许把 FC 指向已知的 feedback-only code object；不得回滚到含 Kimi key 的旧生成包，也不得通过回滚改变老师凭证、老师存储键、RAM 权限或 OSS 对象。

任何删除 bucket、function、role、policy、任务或评价对象的动作都需要单独授权。
