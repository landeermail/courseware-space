# Courseware Space：帮助老师把物理过程带进课堂

很多物理题的困难，不只是不会列式，而是学生看不见运动怎样发生、状态怎样交接、图像怎样形成。Courseware Space 把这些难以仅靠题图和语言重建的过程，变成老师可以直接用于课堂的互动课件。

## 精选课件

- **[474：纵波弹簧标记点](https://landeermail.github.io/courseware-space/preview/TNlUdPGF-r2ZDQ4ZDFWYHS8ERlIxaUJT/q474-v1-39e8e4f62f4b/)**：同步观察弹簧质点的左右振动、疏密结构的传播，以及静态点图中的波长和振幅。

- **[688：多阶段滑轨能量](https://landeermail.github.io/courseware-space/preview/TNlUdPGF-r2ZDQ4ZDFWYHS8ERlIxaUJT/q688-v1-c928e6c7df79/)**：沿关键事件追踪小球的运动、转向和能量变化，理解不同阶段怎样自然衔接。

- **[689：斜面弹簧与速度图像](https://landeermail.github.io/courseware-space/preview/TNlUdPGF-r2ZDQ4ZDFWYHS8ERlIxaUJT/q689-v2-c1703260155c/)**：同步观察弹簧压缩、合力、加速度和速度图像斜率，看到图像怎样从运动过程中形成。

- **[690：弹跳笔的碰撞与能量](https://landeermail.github.io/courseware-space/preview/TNlUdPGF-r2ZDQ4ZDFWYHS8ERlIxaUJT/q690-v2-d0280b4f0831/)**：连续观察碰后上升、碰撞交接、弹簧做功和能量损失，分清各阶段的物理关系。

- **[691：传送带调速与平抛落点](https://landeermail.github.io/courseware-space/preview/TNlUdPGF-r2ZDQ4ZDFWYHS8ERlIxaUJT/q691-v1-5eef1be21733/)**：观察传送带怎样决定离开速度，以及这个速度怎样成为平抛初速度并生成落点与图像。

## 为老师的课堂服务

- 每个教学单元只推进当前需要建立的物理判断；
- 模型、图像、讲解和操作共同呈现同一段关系；
- 动画帮助学生建立想象，播放节奏和课堂路线由老师掌握；
- 原题可以随时调出，但不长期占据教学画面。

课件不替老师讲课，也不默认展开整道题的全部推导。它把最难靠语言重建的部分变得可观察，让老师少做重复说明，把注意力留给真正的课堂判断。

## 公开仓库边界

本仓库只保存已经批准公开的静态课件、展示内容及 GitHub Pages 所需的最小构建校验。研发实验、生产记录、老师反馈、评价服务和内部方法保存在独立私有仓库。

公开展示不代表放弃知识产权或授予复制、修改、再发布、销售许可；具体边界见 [`LICENSE.md`](LICENSE.md)。题目、图片等第三方材料的权利仍归各自权利人所有。

## 本地检查

项目没有前端编译步骤，也不需要 npm：

```bash
python3 -m http.server 8000 --directory site
```

课件可以通过对应的 `site/` 路径直接打开。提交公开站点改动前运行：

```bash
python3 -m unittest discover -s scripts -p "test_*.py"
python3 scripts/validate_site.py
```

`main` 受保护；所有正常变更通过 Pull Request 校验后部署到 GitHub Pages。
