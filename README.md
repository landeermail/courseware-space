# 物理 3D 交互课件库

这是一个以静态 HTML、CSS 和 JavaScript 构建的物理交互课件集合。仓库根目录提供统一入口，各课件保存在独立目录中，并通过 GitHub Pages 发布。

## 本地预览

本项目没有构建步骤，也不需要安装 npm 依赖。在仓库根目录启动静态服务器：

```bash
python3 -m http.server 8000
```

然后访问 <http://localhost:8000/>。不要直接双击打开 HTML 文件；部分浏览器功能和相对资源需要通过 HTTP 正常加载。

## 目录结构

```text
.
├── index.html                 # 课件库首页和课件清单
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

