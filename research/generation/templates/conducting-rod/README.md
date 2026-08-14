# 匀强磁场滑动导体杆模板

这是生成平台 MVP 的首个窄题型模板，范围限定为：闭合平行导轨、直导体杆平动、匀强磁场垂直导轨平面、定值总电阻、杆做匀速运动。

AI 只允许填写 `cases/*.json` 所示的结构化字段。`physics.py` 负责范围校验、方向判定和全部数值推导；不得由 AI 生成或覆盖物理公式。

模板锁定以下关系：

- 动生电动势 `E = BLv`；
- 回路电流 `I = E/R`；
- 安培力 `F = BIL`，方向始终阻碍相对运动；
- 感应磁场阻碍磁通量变化；
- 匀速时外力机械功率 `Fv` 等于焦耳功率 `I²R`。

生成和检查示例：

```bash
python3 research/generation/templates/conducting-rod/render_examples.py
python3 research/generation/templates/conducting-rod/render_examples.py --check
python3 research/generation/validate.py
```

示例页面：

- `examples/rightward-into/index.html`
- `examples/leftward-out/index.html`

这不是全体电磁感应题的通用模板。旋转导体、时变磁场、非匀速动力学、含电源或多杆耦合等情形必须拒绝并进入人工处理。
