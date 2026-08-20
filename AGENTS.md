# AGENTS.md

本仓库是 Courseware Space 的公开展示与 GitHub Pages 发布仓库。产品知识、研发实验、生产控制面、评价服务和老师证据位于独立私有研发仓库，不得写入本仓库。

## 允许范围

- `site/`：已经批准公开的静态课件、公开首页、老师稳定题库和评价页面；
- `scripts/`：Pages 白名单打包、静态校验及对应测试；
- `.github/workflows/`：公开站点校验和 Pages 部署；
- `README.md`、`LICENSE.md`：公开项目说明与版权边界。

不得新增 `research/`、`production/`、`services/`、内部 `docs/`、`CONTEXT.md`、`PROGRESS.md`、`BLOCKED.md`、老师原话、实验记录、提示词、密钥或云端配置。

## 修改与发布

- 从最新 `main` 创建范围明确的分支，通过 Pull Request 合并；禁止直接推送、删除或强制更新 `main`。
- 课件 revision 不可变；新发布使用新的小写英文、数字和连字符目录。
- 只复制本次明确获准公开的精确文件，不得把私有仓库分支或根目录整体推送到本仓库。
- 公开仓库如先做紧急线上修复，必须把精确修复回写私有研发仓库，避免双源漂移。
- 保持现有仓库名、Pages URL、老师长期链接和既有 revision 路径不变。

## 验证

```bash
python3 -m unittest discover -s scripts -p "test_*.py"
python3 scripts/validate_site.py
```

涉及页面时，再通过本地 HTTP 服务检查首页、指定课件、资源、控制台、桌面和 iPad 横屏。任何外部写入、发布或 Git 操作仍需用户明确授权。
