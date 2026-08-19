# 课件生成 harness

> 状态：暂停的历史研发脚手架。现有代码与验收证据继续保留，但不用于下一道真实题的默认实验，也不按既有规模预设继续扩题型；恢复前须重新核验 ADR 0003、0004、0011 和供应商现状。

本目录验证模型自由生成完整课件代码时，物理正确性是否能由模型外部护栏兜底。

- `assertions.py`：领域无关的具名断言、量纲和 fail-closed 报告；
- `domains/`：抛体与圆周的独立参考物理，不读取模型的自评；
- `sandbox.py`：在 Node `vm` 中执行模型生成的纯物理 `sample(input)`；上下文不提供网络、文件系统、`process` 或 `require`，并拒绝随机数与时钟以保证复验；
- `primitives.js`：统一物理时间、演示倍率、回放和状态通知；
- `confirmation.py`：15 分钟有效的一次性老师确认令牌，题型或参数改变后不可复用；
- `contracts.py`：完整 HTML 与纯物理代码的严格生成物契约，并为最终页面注入默认拒绝网络、表单、对象和框架的 CSP。

渲染器还会验证首次 `sample()` 与老师确认场景完全一致、记录运行时错误和时间轴状态；引号字符串中的真实换行会被确定性规范化为 `\n`，除此之外的脚本错误仍然拒绝。时间轴创建即发出 `0 s / paused`，禁止把加载完成误作自动播放。

模型仍可自由决定教学布局、SVG、因果呈现和交互方式，但展示层必须消费已通过沙箱断言的 `coursewareModel.sample()` 状态。机器校验不替代老师对教学表现力的验收。

研发模型策略：harness 固定使用常规速度 `k3-256k` 与 `reasoning_effort=high`，启用 JSON Mode、阶段输出预算和不含业务内容的缓存键。代码拒绝 K2.7 fallback、1M K3、HighSpeed 及 `HARNESS_KIMI_MODEL` 环境变量切换；读取超时与长度截断不自动重试。

最终交付前用 `audit_acceptance.py` 核对两个领域各 5 个真实生成物、逐件浏览器验收和至少 3 类红→绿；reference-only 证据会被明确拒绝。当前完整命令见 `docs/harness/feasibility.md`。
