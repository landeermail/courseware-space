# 机翼电势差三维课件

这是一个可部署到 GitHub Pages 的静态网页课件。部署后可在电脑、iPad Safari 中打开；iPad 可通过“分享 -> 添加到主屏幕”作为类似 App 的入口使用。

## 文件结构

```text
index.html
manifest.webmanifest
sw.js
original-question.jpg
assets/
  three.min.js
  OrbitControls.js
icons/
  icon.svg
```

## GitHub Pages 部署步骤

1. 在 GitHub 新建一个公开仓库，例如 `mh370-physics-courseware`。
2. 上传本文件夹里的所有文件到仓库根目录。
3. 进入仓库 `Settings -> Pages`。
4. `Source` 选择 `Deploy from a branch`。
5. `Branch` 选择 `main`，文件夹选择 `/root`，保存。
6. 等待 1-3 分钟，GitHub 会生成访问链接。

## iPad 使用

1. 用 Safari 打开 GitHub Pages 链接。
2. 横屏使用。
3. 点 Safari 的“分享”按钮。
4. 选择“添加到主屏幕”。
5. 第一次打开需要联网；打开一次后，核心课件资源会被缓存。
