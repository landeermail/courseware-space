"""Generate, sandbox, assert, retry, and preserve model-generated courseware."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from harness.assertions import AssertionFailure
from harness.confirmation import TeacherConfirmationGate
from harness.contracts import ContractError, GeneratedArtifact, GeneratedModel, GeneratedView
from harness.domains.circular import circular_probe_inputs, validate_circular
from harness.domains.projectile import projectile_probe_inputs, validate_projectile
from harness.sandbox import SandboxError, execute_model


PROMPT_VERSION = "harness-free-code-v5-runtime-normalize"
HERE = Path(__file__).resolve().parent
TERMINAL_PROVIDER_KINDS = {
    "configuration",
    "authentication",
    "permission",
    "quota",
    "read_timeout",
    "length_limit",
}


class CompletionClient(Protocol):
    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        artifact_id: str,
        prompt_version: str,
    ) -> str: ...


class HarnessGenerationError(RuntimeError):
    def __init__(self, message: str, *, kind: str = "harness") -> None:
        super().__init__(message)
        self.kind = kind


@dataclass(frozen=True)
class HarnessGenerationResult:
    id: str
    domain: str
    status: str
    attempts: int
    output_path: str
    reports: tuple[dict[str, Any], ...]
    teaching_intent: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "domain": self.domain,
            "status": self.status,
            "attempts": self.attempts,
            "output_path": self.output_path,
            "reports": list(self.reports),
            "teaching_intent": self.teaching_intent,
        }


DOMAIN_CONTRACTS = {
    "projectile": """sample(input) 接收 input.scenario 与 input.times_s。返回且只返回：
{"states":[{"t_s","x_m","y_m","vx_m_s","vy_m_s","ax_m_s2","ay_m_s2","kinetic_j","potential_j","mechanical_j"}],"events":{"flight_time_s","range_m","apex_time_s","max_height_m","optimal_equal_height_angle_deg"}}。
必须对 horizontal/oblique 与任意合法速度、角度、高度、质量、重力参数动态计算，落地后的 y 取 0。""",
    "circular": """sample(input) 接收 input.scenario 与 input.angles_rad。返回且只返回：
{"states":[{"angle_rad","x_m","y_m","speed_m_s","ax_m_s2","ay_m_s2","radial_force_n","tension_n","kinetic_j","potential_j","mechanical_j"}],"events":{"period_s","centripetal_acceleration_m_s2"}}；仅当 mode=vertical_string 时 events 另含 "critical_top_speed_m_s","critical_bottom_speed_m_s"。
必须对 uniform/orbit/vertical_string 和任意合法质量、半径、速度或中心天体质量动态计算；vertical_string 的 angle=0 是最低点，速度随高度变化，period_s 必须由 dt=r·dθ/v(θ) 数值积分，不能用 2πr/v_最低点；orbit 由 G、中心质量、半径决定速度。""",
}


MODEL_SYSTEM_PROMPT = """你是物理互动课件的纯物理 JavaScript 模型生成器。不能决定自己的物理是否正确；外部 harness 会在沙箱中用未知参数复算并逐条断言。

只输出单一 JSON 对象，不要 Markdown、代码围栏或解释，字段必须恰好为：
{"title":"中文标题","domain":"projectile 或 circular","model_js":"纯 JavaScript 物理模型"}

硬约束：
1. model_js 设置 globalThis.coursewareModel=Object.freeze({sample(input){...}})，只读 input 并返回 JSON；不得访问 DOM、网络、文件、计时器、随机数、process、require、eval 或动态代码。
2. 不得硬编码题设答案。harness 会改变参数重跑同一 sample()。
"""

VIEW_SYSTEM_PROMPT = """你是物理互动课件教学界面生成器。物理模型已经被外部 harness 独立验收；你只负责自由设计完整 HTML、CSS、SVG 与交互，不得在 HTML 中另写一套物理公式。

只输出单一 JSON 对象，不要 Markdown、代码围栏或解释，字段必须恰好为：
{"teaching_intent":"说明要让学生观察、操控、验证的不可见过程","html":"完整 HTML"}

硬约束：
1. HTML 不用外部资源、网络、存储或动态执行；必须包含且各只使用一次 <!--HARNESS_PRIMITIVES-->、<!--HARNESS_MODEL-->、<!--HARNESS_INPUT-->。三个占位符必须作为 HTML 节点放在所有 script 标签之外，绝不能写进某段 JavaScript 内部。
2. 交互脚本从 globalThis.__HARNESS_INPUT__ 读取确认场景并调用 coursewareModel.sample(input)。时间轴必须且只能使用：CoursewarePrimitives.createTimeline({durationPhysicalS: 正数秒, onChange(state){...}})。state 含 physicalTimeS、demoRate、playing；控制器只使用 play()、pause()、replay()、seek(物理秒)、setDemoRate(0.1到4)。不得自己调用 requestAnimationFrame 或实现备用时间轴。
3. 页面至少包含两个可调参数控件 data-control、一个物理时间读数 data-physical-time、一个演示倍率读数 data-demo-time、状态读数 data-readout、回放按钮 data-replay。触控目标至少 44px。
4. 必须明确区分物理时间与演示倍率：用 CoursewarePrimitives.formatPhysicalTime(state.physicalTimeS) 写入 data-physical-time，用 CoursewarePrimitives.formatDemoRate(state.demoRate) 写入 data-demo-time；允许慢放、暂停、拖动。页面要呈现运动、速度/加速度或受力方向、能量/临界变化之间的因果，不做自动播放解题步骤。
5. 交互参数改变时重新构造合法 scenario 和采样轴后调用 sample()，不能在 HTML 里计算物理量。动画显示只消费 sample() 返回的 states/events。
6. 中文界面，响应桌面与 375px；不依赖 hover；持续动画可暂停并在 document.hidden 时暂停。请把 HTML 控制在约 16000 字符以内。
7. JSON 解码后的 HTML 中，每段内联 JavaScript 都必须能直接通过语法检查。禁止在单引号或双引号字符串中放入真实换行；需要换行时使用模板字符串，或在 JSON 中把反斜杠双重转义为 \\n。输出前自行检查引号、模板字符串与括号是否闭合。
8. 首次调用 sample() 前，必须先把每个参数控件从 globalThis.__HARNESS_INPUT__.scenario 的对应字段初始化；首次 sample() 传入的 scenario 必须与老师确认场景字段和值完全一致，不能用控件中点、硬编码默认值或 fallback 覆盖题设。只有用户修改控件后才构造变化场景。
9. 首屏必须暂停在物理时间 0，不得在加载、初始化或重采样时调用 play() 或 replay()；播放只能由用户点击触发。
"""


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class HarnessPipeline:
    def __init__(self, client: CompletionClient, confirmation_gate: TeacherConfirmationGate) -> None:
        self.client = client
        self.confirmation_gate = confirmation_gate
        self.primitive_js = (HERE / "primitives.js").read_text(encoding="utf-8")

    def _probes(self, domain: str, scenario: dict[str, Any]) -> list[dict[str, Any]]:
        return projectile_probe_inputs(scenario) if domain == "projectile" else circular_probe_inputs(scenario)

    def _validator(self, domain: str) -> Any:
        return validate_projectile if domain == "projectile" else validate_circular

    @staticmethod
    def _validate_probe(domain: str, validator: Any, model_input: dict[str, Any], output: dict[str, Any]) -> Any:
        axis = model_input["times_s"] if domain == "projectile" else model_input["angles_rad"]
        return validator(model_input["scenario"], output, axis)

    def _complete_phase(
        self,
        phase: str,
        system_prompt: str,
        user_prompt: str,
        artifact_id: str,
    ) -> tuple[str, dict[str, Any] | None]:
        method = getattr(self.client, f"complete_{phase}", None)
        callable_method = method if callable(method) else self.client.complete
        raw = callable_method(
            system_prompt,
            user_prompt,
            artifact_id=artifact_id,
            prompt_version=PROMPT_VERSION,
        )
        take_metadata = getattr(self.client, "take_last_metadata", None)
        metadata = take_metadata() if callable(take_metadata) else None
        return raw, metadata

    def generate(
        self,
        *,
        artifact_id: str,
        domain: str,
        question: str,
        scenario: dict[str, Any],
        confirmation_token: str,
        output_dir: Path,
        max_attempts: int = 3,
    ) -> HarnessGenerationResult:
        if domain not in DOMAIN_CONTRACTS:
            raise HarnessGenerationError("harness 只验证 projectile/circular")
        if not isinstance(question, str) or not 12 <= len(question.strip()) <= 1000:
            raise HarnessGenerationError("题目文本长度无效")
        if not 1 <= max_attempts <= 3:
            raise HarnessGenerationError("重试次数必须在 1～3")
        probes = self._probes(domain, scenario)  # Normalize before consuming the teacher token.
        self.confirmation_gate.consume(confirmation_token, domain, scenario)
        output_dir.mkdir(parents=True, exist_ok=True)
        model_attempt_dir = output_dir / "model-attempts"
        view_attempt_dir = output_dir / "view-attempts"
        model_attempt_dir.mkdir(exist_ok=True)
        view_attempt_dir.mkdir(exist_ok=True)
        feedback = ""
        failure_messages: list[str] = []

        artifact_model: GeneratedModel | None = None
        reports: list[dict[str, Any]] = []
        model_attempt = 0
        model_provider_failures = 0
        for attempt in range(1, max_attempts + 1):
            model_attempt = attempt
            user_prompt = (
                f"题目：{question.strip()}\n"
                f"老师已确认场景 JSON：{json.dumps(scenario, ensure_ascii=False, sort_keys=True)}\n"
                f"领域输出契约：\n{DOMAIN_CONTRACTS[domain]}\n"
                "生成可供任意教学界面调用的纯物理模型。"
            )
            if feedback:
                user_prompt += f"\n上一次被外部 harness 拒绝，必须修正这些真实失败后重新完整输出：\n{feedback}"
            attempt_record: dict[str, Any] = {
                "attempt": attempt,
                "prompt_version": PROMPT_VERSION,
                "ran_at": datetime.now(timezone.utc).isoformat(),
                "raw": "",
            }
            try:
                raw, provider_metadata = self._complete_phase(
                    "model", MODEL_SYSTEM_PROMPT, user_prompt, artifact_id
                )
                attempt_record["raw"] = raw
                if provider_metadata is not None:
                    attempt_record["provider"] = provider_metadata
            except RuntimeError as error:
                feedback = f"模型传输失败：{error}。请重新输出完整 JSON。"
                failure_messages.append(feedback)
                model_provider_failures += 1
                failure_kind = getattr(error, "kind", "provider")
                attempt_record.update(
                    {
                        "status": "provider_failed",
                        "failure_kind": failure_kind,
                        "failure": feedback,
                    }
                )
                error_metadata = getattr(error, "metadata", None)
                if isinstance(error_metadata, dict):
                    attempt_record["provider"] = error_metadata
                _write_json(model_attempt_dir / f"{attempt:02d}.json", attempt_record)
                if failure_kind in TERMINAL_PROVIDER_KINDS:
                    break
                continue
            try:
                artifact_model = GeneratedModel.parse(raw, domain)
                reports = []
                validator = self._validator(domain)
                for probe_index, model_input in enumerate(probes):
                    output = execute_model(artifact_model.model_js, model_input)
                    assertion_report = self._validate_probe(domain, validator, model_input, output)
                    reports.append({"probe": probe_index, **assertion_report.as_dict()})
                    assertion_report.require()
                attempt_record.update({"status": "passed", "reports": reports})
                _write_json(model_attempt_dir / f"{attempt:02d}.json", attempt_record)
                break
            except (ContractError, SandboxError, AssertionFailure, ValueError) as error:
                if isinstance(error, AssertionFailure):
                    failed = [check.message for check in error.report.checks if not check.passed][:12]
                    feedback = "\n".join(failed)
                else:
                    feedback = str(error)
                failure_messages.append(feedback)
                attempt_record.update({"status": "rejected", "failure": feedback})
                _write_json(model_attempt_dir / f"{attempt:02d}.json", attempt_record)
        if artifact_model is None:
            provider_unavailable = model_attempt > 0 and model_provider_failures == model_attempt
            length_limited = any("输出达到长度上限" in message for message in failure_messages)
            status = "output_limited" if length_limited else ("provider_unavailable" if provider_unavailable else "rejected")
            _write_json(
                output_dir / "failure.json",
                {"phase": "model", "status": status, "attempts": model_attempt, "max_attempts": max_attempts, "failures": failure_messages},
            )
            if status in {"provider_unavailable", "output_limited"}:
                raise HarnessGenerationError(
                    f"{artifact_id} 生成服务在 {model_attempt} 次尝试后不可用，尚未进入物理判定",
                    kind=status,
                )
            raise HarnessGenerationError(f"{artifact_id} 物理模型在 {max_attempts} 次内未通过 harness")

        view_feedback = ""
        artifact_view: GeneratedView | None = None
        view_attempt = 0
        view_provider_failures = 0
        for attempt in range(1, max_attempts + 1):
            view_attempt = attempt
            view_prompt = (
                f"题目：{question.strip()}\n"
                f"老师已确认场景 JSON：{json.dumps(scenario, ensure_ascii=False, sort_keys=True)}\n"
                f"标题：{artifact_model.title}\n"
                f"物理模型输入输出契约：\n{DOMAIN_CONTRACTS[domain]}\n"
                "请自由设计能帮助学生构建时空与因果理解的完整课件界面。"
            )
            if view_feedback:
                view_prompt += f"\n上一次 HTML 被契约拒绝，必须修正后重新完整输出：\n{view_feedback}"
            attempt_record = {"attempt": attempt, "prompt_version": PROMPT_VERSION, "ran_at": datetime.now(timezone.utc).isoformat(), "raw": ""}
            try:
                raw, provider_metadata = self._complete_phase(
                    "view", VIEW_SYSTEM_PROMPT, view_prompt, artifact_id
                )
                attempt_record["raw"] = raw
                if provider_metadata is not None:
                    attempt_record["provider"] = provider_metadata
            except RuntimeError as error:
                provider_failure = f"视图传输失败：{error}。请重新输出完整 JSON。"
                failure_messages.append(provider_failure)
                view_provider_failures += 1
                failure_kind = getattr(error, "kind", "provider")
                attempt_record.update(
                    {
                        "status": "provider_failed",
                        "failure_kind": failure_kind,
                        "failure": provider_failure,
                    }
                )
                error_metadata = getattr(error, "metadata", None)
                if isinstance(error_metadata, dict):
                    attempt_record["provider"] = error_metadata
                _write_json(view_attempt_dir / f"{attempt:02d}.json", attempt_record)
                if failure_kind in TERMINAL_PROVIDER_KINDS:
                    break
                continue
            try:
                artifact_view = GeneratedView.parse(raw)
                attempt_record.update({"status": "passed", "normalizations": list(artifact_view.normalizations)})
                _write_json(view_attempt_dir / f"{attempt:02d}.json", attempt_record)
                break
            except ContractError as error:
                view_feedback = str(error)
                failure_messages.append(view_feedback)
                attempt_record.update({"status": "rejected", "failure": view_feedback})
                _write_json(view_attempt_dir / f"{attempt:02d}.json", attempt_record)
        if artifact_view is None:
            provider_unavailable = view_attempt > 0 and view_provider_failures == view_attempt
            length_limited = any("输出达到长度上限" in message for message in failure_messages)
            status = "output_limited" if length_limited else ("provider_unavailable" if provider_unavailable else "rejected")
            _write_json(
                output_dir / "failure.json",
                {"phase": "view", "status": status, "attempts": view_attempt, "max_attempts": max_attempts, "failures": failure_messages},
            )
            if status in {"provider_unavailable", "output_limited"}:
                raise HarnessGenerationError(
                    f"{artifact_id} 教学界面生成服务在 {view_attempt} 次尝试后不可用，尚未进入契约判定",
                    kind=status,
                )
            raise HarnessGenerationError(f"{artifact_id} 教学界面在 {max_attempts} 次内未通过契约")

        artifact = GeneratedArtifact(
            title=artifact_model.title,
            domain=artifact_model.domain,
            teaching_intent=artifact_view.teaching_intent,
            model_js=artifact_model.model_js,
            html=artifact_view.html,
        )
        rendered = artifact.render(self.primitive_js, probes[0])
        (output_dir / "index.html").write_text(rendered, encoding="utf-8")
        (output_dir / "model.js").write_text(artifact.model_js + "\n", encoding="utf-8")
        _write_json(output_dir / "source.json", artifact.as_dict())
        _write_json(output_dir / "assertion-report.json", {"passed": True, "reports": reports})
        result = HarnessGenerationResult(
            id=artifact_id,
            domain=domain,
            status="succeeded",
            attempts=model_attempt + view_attempt,
            output_path=str(output_dir / "index.html"),
            reports=tuple(reports),
            teaching_intent=artifact.teaching_intent,
        )
        _write_json(
            output_dir / "metadata.json",
            {
                **result.as_dict(),
                "model_attempts": model_attempt,
                "view_attempts": view_attempt,
                "view_normalizations": list(artifact_view.normalizations),
            },
        )
        return result
