# 物理互动课件与生成平台

这是一个用模型、动画和交互帮助学生跨越“想象鸿沟”的物理课件项目。GitHub Pages 只承载公开静态课件、老师题库与评价页面；仓库另行保留不进入 Pages 的本地课件生成实验和阿里云部署工具。

## 本地预览

本项目没有前端编译步骤，也不需要安装 npm 依赖。在仓库根目录启动静态服务器：

```bash
python3 -m http.server 8000 --directory site
```

然后访问 <http://localhost:8000/>。不要直接双击打开 HTML 文件；部分浏览器功能和相对资源需要通过 HTTP 正常加载。

如果需要使用老师课件生成器，请通过本地生成服务启动：

```bash
KIMI_API_KEY="$(security find-generic-password -a "$USER" -s courseware-space-kimi -w)" \
  python3 server/app.py
```

然后访问 <http://localhost:8000/generator/>。生成器后端、密钥管理和验收方法见 `server/README.md`。

文字、图片和 PDF 三种输入已经合并在 <http://localhost:8000/generator/>。图片/PDF 必须经过老师逐项确认后才会生成。该生成服务目前只供本地研发；公网 FC 已收缩为不含模型凭证的评价服务，`/api/generate` 保持关闭。当前部署结构见 [`docs/deploy/architecture.md`](docs/deploy/architecture.md)。

## 先读什么

- [`CONTEXT.md`](CONTEXT.md)：产品使命、术语和长期边界；
- [`docs/quality/standard.md`](docs/quality/standard.md)：物理正确之后的六维质量标准；
- [`docs/adr/`](docs/adr/)：已采纳的重要取舍；
- [`PROGRESS.md`](PROGRESS.md)：实现与验收历史；[`BLOCKED.md`](BLOCKED.md) 只列仍待处理事项；
- [`docs/goals/`](docs/goals/)：历史任务书归档，不代表当前待办。

## 课件质量与老师试用

物理正确性通过后，课件按[好课件六维标准](docs/quality/standard.md)评价：因果呈现、过程可见、有效交互、任务驱动、可验证性、与解题的衔接。老师可在 <http://localhost:8000/trial/> 逐维记录反馈并导出 JSON；反馈格式和本地校验命令见 `feedback/README.md`，第一次试用流程见 `trial/protocol.md`。

当前老师提供的是允许公开的练习题。正式静态课件只通过 GitHub Pages 发布，每个精确 revision 使用不可变目录；OSS 私有课件投递工具已经冻结，不再是生产渠道。老师使用一条长期稳定的题库链接进入课件和“我的评价”；评价任务、当前结果与历史版本以服务端精确 revision 记录为准。

## 目录结构

```text
.
├── site/                      # 唯一 Pages 静态产品源，内部结构即公开 URL
├── generator/                 # 老师生成页面和已验证生成产物
├── templates/                 # 锁定物理关系的参数化课件模板
├── server/                    # 本地异步生成服务与真实验收证据
├── harness/                   # 自由生成与物理护栏的研发验证
├── library/                   # 经验收生成课件的元数据与晋升区
├── trial/                     # 六维工具、历史试用协议与单题生产候选
├── feedback/                  # 结构化反馈 schema 与本地校验器
├── production/                # 受版本控制的单题当前生产状态
├── deploy/                    # feedback-only FC、OSS 与域名切换工具
├── docs/                      # ADR、质量、部署与历史任务书
└── .github/workflows/         # GitHub Pages 部署工作流
```

每个课件目录以 `index.html` 为入口，并将图片、脚本、图标等专用资源保存在同一目录或其子目录中。

## 添加或修改课件

一道题进入正式生产后统一使用 `$build-physics-courseware` 和版本化的 `production/courseware/<courseware_id>/record.md`：当前产品协调任务确认物理与教学方案，短期前端执行者只实现候选和 A0，独立评审者检查精确修订，结论回到产品检查点。获发布授权后，产品协调者从最新 `main` 建隔离分支，把候选字节写入不可变 revision，只更新对应老师题库卡片并通过 PR 合并。Pages 部署后必须从老师真实长期入口验 revision、资源和评价入口。

## 发布

推送或合并到 `main` 后，[GitHub Actions](https://github.com/landeermail/courseware-space/actions) 会通过 `scripts/build_pages.py` 组装 `site/` 白名单工件并部署到 GitHub Pages：

<https://landeermail.github.io/courseware-space/>

除非正在处理紧急修复，否则不要直接向 `main` 推送。
