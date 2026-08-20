# Courseware Space：高中物理互动课件

把题目中难以想象的运动、变化和因果过程，变成老师可以直接用于课堂的可观察、可操控互动课件。

**[打开公开课件库](https://landeermail.github.io/courseware-space/)**

## 精选课件

| 题目 | 学生原本难以看见的过程 | 在线体验 |
|---|---|---|
| 474：纵波弹簧标记点 | 弹簧质点如何左右振动，疏密结构如何向右传播，以及怎样从静态点图回到波长和振幅 | [体验纵波课件](https://landeermail.github.io/courseware-space/preview/TNlUdPGF-r2ZDQ4ZDFWYHS8ERlIxaUJT/q474-v1-39e8e4f62f4b/) |
| 20：旋转导体与电磁感应 | 转动、电流、安培力和运动状态如何形成连续因果链 | [体验旋转导体课件](https://landeermail.github.io/courseware-space/electromagnetism/q20-rotating-rod/) |
| 23：落管与上抛小球 | 在地面与落管两个参考系中，怎样理解相对运动和穿出条件 | [体验相对运动课件](https://landeermail.github.io/courseware-space/mechanics/q23-falling-tube-ball/) |

## 我们怎样做课件

- 从学生真正“想象不出来”的过程出发，而不是默认自动讲完整道题；
- 动画和交互只服务当前理解障碍，并能回到题图、条件和纸笔判断；
- AI负责扩大实现能力，物理、教学范围、用户体验和发布仍由人独立检查与决定；
- 老师可以自由反馈，不需要填写固定评价表。

学生在老师组织下参与学习，当前产品首先服务于老师的课堂表达和判断。

## 公开仓库边界

本仓库只保存公开静态课件、展示内容及 GitHub Pages 所需的最小构建校验。研发实验、生产记录、老师反馈、评价服务和内部方法保存在独立私有仓库。

公开展示不代表放弃知识产权或授予复制、修改、再发布、销售许可；具体边界见 [`LICENSE.md`](LICENSE.md)。题目、图片等第三方材料的权利仍归各自权利人所有。

## 本地预览

项目没有前端编译步骤，也不需要 npm：

```bash
python3 -m http.server 8000 --directory site
```

访问 <http://localhost:8000/>。提交公开站点改动前运行：

```bash
python3 -m unittest discover -s scripts -p "test_*.py"
python3 scripts/validate_site.py
```

`main` 受保护；所有正常变更通过 Pull Request 校验后部署到 GitHub Pages。
