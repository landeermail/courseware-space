# 物理 3D 交互课件库

这是一个以静态 HTML、CSS 和 JavaScript 构建的物理交互课件集合。仓库根目录提供统一入口，各课件保存在独立目录中，并通过 GitHub Pages 发布。

## 本地预览

本项目没有构建步骤，也不需要安装 npm 依赖。在仓库根目录启动静态服务器：

```bash
python3 -m http.server 8000
```

然后访问 <http://localhost:8000/>。不要直接双击打开 HTML 文件；部分浏览器功能和相对资源需要通过 HTTP 正常加载。

如果需要使用老师课件生成器，请通过本地生成服务启动：

```bash
KIMI_API_KEY="$(security find-generic-password -a "$USER" -s courseware-space-kimi -w)" \
  python3 server/app.py
```

然后访问 <http://localhost:8000/generator/>。生成器后端、密钥管理和验收方法见 `server/README.md`。

文字、图片和 PDF 三种输入已经合并在 <http://localhost:8000/generator/>。图片/PDF 必须经过老师逐项确认后才会生成。阿里云 FC + OSS 的部署结构、可复跑命令和安全边界见 `deploy/README.md` 与 `docs/deploy/`；当前云端状态以 `PROGRESS.md` 与 `BLOCKED.md` 为准，不能用本地结果代替公网验收。

## 课件质量与老师试用

物理正确性通过后，课件按[好课件六维标准](docs/quality/standard.md)评价：因果呈现、过程可见、有效交互、任务驱动、可验证性、与解题的衔接。老师可在 <http://localhost:8000/trial/> 逐维记录反馈并导出 JSON；反馈格式和本地校验命令见 `feedback/README.md`，第一次试用流程见 `trial/protocol.md`。

老师提供的内部试题不进入公开仓库或 GitHub Pages。完整题页只生成在被 Git 忽略的 `trial/private/`，需要在两台电脑之间通过私有渠道单独同步。

## 目录结构

```text
.
├── index.html                 # 课件库首页和课件清单
├── generator/                 # 老师生成页面和已验证生成产物
├── templates/                 # 锁定物理关系的参数化课件模板
├── server/                    # 本地异步生成服务与真实验收证据
├── trial/                     # 六维打分工具、试用协议与私有材料模板
├── feedback/                  # 结构化反馈 schema 与本地校验器
├── electromagnetism/          # 电磁学课件
├── helicopter-dynamics/       # 直升机动力学课件
├── mh370-physics/             # MH370 物理分析课件
└── .github/workflows/         # GitHub Pages 部署工作流
```

每个课件目录以 `index.html` 为入口，并将图片、脚本、图标等专用资源保存在同一目录或其子目录中。

## 添加或修改课件

1. 从最新 `main` 创建独立分支：

   ```bash
   git switch main
   git pull --ff-only
   git switch -c feat/<short-name>
   ```

2. 在合适的学科目录下创建或修改课件。
3. 新增课件时，在根目录 `index.html` 的 `coursewareData` 中登记入口。
4. 启动本地服务器，检查首页、课件页面、交互操作和资源加载。
5. 推送分支并通过 Pull Request 合并到 `main`。

## 发布

推送或合并到 `main` 后，[GitHub Actions](https://github.com/landeermail/courseware-space/actions) 会自动将仓库内容部署到 GitHub Pages：

<https://landeermail.github.io/courseware-space/>

除非正在处理紧急修复，否则不要直接向 `main` 推送。
