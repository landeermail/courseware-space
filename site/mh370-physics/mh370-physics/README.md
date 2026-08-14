# 机翼电势差三维课件

这是 `site/` 静态源中的一份 GitHub Pages 课件。合并到 `main` 后由仓库 Pages 白名单工件统一发布；不单独创建仓库或上传仓库根。发布后可在电脑、iPad Safari 中打开；iPad 可通过“分享 -> 添加到主屏幕”作为类似 App 的入口使用。

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

## 本地预览

在仓库根目录运行 `python3 -m http.server 8000 --directory site`，然后访问 <http://localhost:8000/mh370-physics/mh370-physics/>。

## iPad 使用

1. 用 Safari 打开 GitHub Pages 链接。
2. 横屏使用。
3. 点 Safari 的“分享”按钮。
4. 选择“添加到主屏幕”。
5. 第一次打开需要联网；打开一次后，核心课件资源会被缓存。
