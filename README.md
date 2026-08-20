# 面向高中物理老师的互动课件

这是一个帮助高中物理老师把不可见物理过程变成可观察、可操控、可验证时空模型的互动课件项目。学生在老师组织下参与学习，但不是当前产品客户。GitHub Pages 只承载公开静态课件、老师题库与评价页面；评价服务与本地研发资产分别由独立职责模块承担，都不会因为与站点共仓而进入 Pages。

## 本地预览

本项目没有前端编译步骤，也不需要安装 npm 依赖。在仓库根目录启动静态服务器：

```bash
python3 -m http.server 8000 --directory site
```

然后访问 <http://localhost:8000/>。不要直接双击打开 HTML 文件；部分浏览器功能和相对资源需要通过 HTTP 正常加载。

`research/generation/` 中仍保留一套可运行的本地生成器与 harness，但它是暂停的历史研发脚手架，不是下一道真实题的默认入口。只有明确恢复该方向时，才按其 README 启动和验证：

```bash
KIMI_API_KEY="$(security find-generic-password -a "$USER" -s courseware-space-kimi -w)" \
  python3 research/generation/app.py
```

然后访问 <http://localhost:8000/generator/>。生成器后端、密钥管理和验收方法见 `research/generation/README.md`。

该生成服务只供本地研发；公网 FC 已收缩为不含模型凭证的评价服务，`/api/generate` 保持关闭。当前部署结构见 [`docs/deploy/architecture.md`](docs/deploy/architecture.md)。

## 先读什么

- [`CONTEXT.md`](CONTEXT.md)：产品使命、术语和长期边界；
- [`docs/adr/0011-default-to-minimal-courseware-research-experiments.md`](docs/adr/0011-default-to-minimal-courseware-research-experiments.md)：下一道真实题的默认实验方式；
- [`docs/quality/standard.md`](docs/quality/standard.md)：可按需使用的历史六维质量视角；
- [`docs/adr/`](docs/adr/)：已采纳的重要取舍；
- [`PROGRESS.md`](PROGRESS.md)：实现与验收历史；[`BLOCKED.md`](BLOCKED.md) 只列仍待处理事项；
- [`docs/goals/`](docs/goals/)：历史任务书归档，不代表当前待办。

## 下一道真实题默认怎么做

顾问老师给出的下一道真实题先作为研发实验，不自动进入 `production/`，也不自动使用旧 harness、九阶段状态或 A0/A1/A2/A3 评审。产品协调 Work 生成单题 Codex 任务包；单题 Codex 完成物理与教学分析、形成紧凑临时任务书、调用 Kimi Code CLI 实现前端候选并独立检查；用户体验通过并明确批准后，才协调稳定链接给老师试用。

老师可以自由反馈，不要求按六维或结构化 intake 填写。现有评价页面仍是可用的意见入口；老师原意与用户解释必须分开记录。每轮只长期保留最小实验结论，不保存完整调试流水账或把单题经验自动写成通用规则。

## 已发布课件与评价

正式静态课件只通过 GitHub Pages 发布，每个精确 revision 使用不可变目录。老师从原长期题库的“去评价”和“我的评价”进入精确 revision 任务；反馈格式、本地校验和 feedback-only 运行边界见 [`services/feedback/README.md`](services/feedback/README.md)。

当前老师提供的是允许公开的练习题；OSS 私有课件投递工具已经冻结，不再是生产渠道。老师使用一条长期稳定的题库链接进入课件和“我的评价”；评价任务、当前结果与历史版本以服务端精确 revision 记录为准。

## 目录结构

```text
.
├── site/                      # 唯一 Pages 静态产品源，内部结构即公开 URL
├── production/                # 明确转入正式生产后的单题状态与规范输入
├── services/feedback/         # 评价运行时、schema、测试与 feedback-only 部署
├── research/generation/       # 暂停的本地生成器、harness、模板与历史研发证据
├── scripts/                   # Pages 打包、站点校验等仓库级小接口
├── docs/                      # ADR、质量、部署与历史任务书
└── .github/workflows/         # GitHub Pages 部署工作流
```

本机可能仍有被 Git 忽略的 `trial/private/` 恢复保险和 `deploy/dist/` 旧构建产物；它们不是当前源码模块、事实源或发布输入。

每个课件目录以 `index.html` 为入口，并将图片、脚本、图标等专用资源保存在同一目录或其子目录中。

## 正式生产与发布

只有用户明确决定某题转入正式生产时，才重新评估 `$build-physics-courseware` 和 `production/courseware/<courseware_id>/` 中哪些既有协议仍适用。任何写入 `site/`、发布或外部状态变化都需要明确授权；获准发布的候选使用不可变 revision 目录，只更新对应老师题库卡片。Pages 部署后必须从老师真实长期入口验 revision、资源和评价入口。

## 发布

推送或合并到 `main` 后，[GitHub Actions](https://github.com/landeermail/courseware-space/actions) 会通过 `scripts/build_pages.py` 组装 `site/` 白名单工件并部署到 GitHub Pages：

<https://landeermail.github.io/courseware-space/>

除非正在处理紧急修复，否则不要直接向 `main` 推送。
