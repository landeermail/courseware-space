"""Strict question-to-template generation pipeline and asynchronous job manager."""

from __future__ import annotations

import json
import hashlib
import re
import sys
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from kimi_client import KimiCodeClient, ProviderError


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_ROOT = ROOT / "templates" / "conducting-rod"
sys.path.insert(0, str(TEMPLATE_ROOT))

from physics import ModelValidationError, assert_physics, derive_physics, normalize_config  # noqa: E402
from render_examples import render_config  # noqa: E402


PROMPT_VERSION = "conducting-rod-parser-v1"
EXPECTED_OUTER_KEYS = {"supported", "reason", "parameters"}
EXPECTED_PARAMETER_KEYS = {
    "magnetic_field_t",
    "rod_length_m",
    "rod_speed_m_s",
    "resistance_ohm",
    "field_direction",
    "motion_direction",
}

SYSTEM_PROMPT = """你是高中物理题目的严格参数提取器，不负责解题，也不生成代码。

当前模板只支持同时满足以下条件的题目：
1. 闭合平行导轨上的一根直导体杆做平动；
2. 匀强磁场垂直导轨平面；
3. 导体杆明确做匀速直线运动；
4. 题目给出磁感应强度 B、杆长或导轨间距 L、速率 v、回路总电阻或唯一电阻 R；
5. 不含电源、时变磁场、旋转导体、多杆耦合或需要动力学求速度的过程。

只输出一个 JSON 对象，不要 Markdown、代码围栏、解释或额外字段。结构必须恰好为：
{"supported":true,"reason":"","parameters":{"magnetic_field_t":0.5,"rod_length_m":1.0,"rod_speed_m_s":2.0,"resistance_ohm":0.4,"field_direction":"into_page","motion_direction":"right"}}

规则：
- supported 只能是 true 或 false。
- 超出模板范围或缺少任一数值时，输出 {"supported":false,"reason":"简短原因","parameters":null}。
- 所有数值换算为 SI 制纯数字；不要计算题目未给出的 B、L、v、R。
- field_direction 只能是 into_page（垂直纸面/导轨平面向里）或 out_of_page（向外）。
- motion_direction 只能是 left 或 right。
- “其余电阻不计”时，题目给出的电阻就是回路总电阻。
- 不要输出公式、答案、物理代码或任何未列出的参数。
"""
PROMPT_SHA256 = hashlib.sha256(SYSTEM_PROMPT.encode("utf-8")).hexdigest()


@dataclass
class GenerationOutcome:
    status: str
    question: str
    reason: str = ""
    config: dict[str, Any] | None = None
    output_path: str | None = None
    prompt_version: str = PROMPT_VERSION


class ManualRequestRecorder:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()

    def append(self, record: dict[str, Any]) -> None:
        safe_record = {
            **record,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        line = json.dumps(safe_record, ensure_ascii=False, separators=(",", ":"))
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")


def normalize_question(question: object) -> str:
    if not isinstance(question, str):
        raise ValueError("题目必须是文本")
    question = " ".join(question.split())
    if not 12 <= len(question) <= 2000:
        raise ValueError("题目长度必须在 12～2000 个字符之间")
    return question


def parse_ai_response(raw: str) -> tuple[bool, str, dict[str, Any] | None]:
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("AI 返回为空")
    stripped = raw.strip()
    if stripped.startswith("```") or "```" in stripped:
        raise ValueError("AI 返回包含代码围栏")
    try:
        data = json.loads(stripped)
    except json.JSONDecodeError as error:
        raise ValueError(f"AI 返回不是单一 JSON 对象：{error.msg}") from error
    if not isinstance(data, dict) or set(data) != EXPECTED_OUTER_KEYS:
        raise ValueError("AI 返回的顶层字段不符合白名单")
    supported = data["supported"]
    reason = data["reason"]
    parameters = data["parameters"]
    if not isinstance(supported, bool):
        raise ValueError("supported 必须是布尔值")
    if not isinstance(reason, str) or len(reason) > 200:
        raise ValueError("reason 必须是 200 字以内文本")
    if not supported:
        if parameters is not None:
            raise ValueError("范围外结果的 parameters 必须为 null")
        return False, reason.strip() or "题目超出当前模板范围", None
    if reason.strip():
        raise ValueError("范围内结果的 reason 必须为空")
    if not isinstance(parameters, dict) or set(parameters) != EXPECTED_PARAMETER_KEYS:
        raise ValueError("AI 参数字段不符合白名单")
    return True, "", parameters


def build_template_config(question: str, parameters: dict[str, Any]) -> dict[str, Any]:
    motion = parameters["motion_direction"]
    title_direction = "向右" if motion == "right" else "向左" if motion == "left" else "未知方向"
    raw_config = {
        "schema_version": 1,
        "title": f"匀强磁场中的滑动导体杆：{title_direction}切割",
        "source_text": question,
        **parameters,
        "duration_s": 2.0,
    }
    config = normalize_config(raw_config)
    assert_physics(config, derive_physics(config))
    return config


class GenerationService:
    def __init__(self, client: KimiCodeClient, recorder: ManualRequestRecorder) -> None:
        self.client = client
        self.recorder = recorder

    def generate_sync(self, question: object, output_dir: Path, request_id: str | None = None) -> GenerationOutcome:
        request_id = request_id or uuid.uuid4().hex[:12]
        try:
            normalized_question = normalize_question(question)
        except ValueError as error:
            return GenerationOutcome("manual_required", str(question), str(error))

        try:
            raw = self.client.complete(SYSTEM_PROMPT, normalized_question)
            supported, reason, parameters = parse_ai_response(raw)
            if not supported or parameters is None:
                outcome = GenerationOutcome("manual_required", normalized_question, reason)
            else:
                config = build_template_config(normalized_question, parameters)
                html = render_config(config)
                output_dir.mkdir(parents=True, exist_ok=True)
                output_path = output_dir / "index.html"
                output_path.write_text(html, encoding="utf-8")
                try:
                    display_path = str(output_path.relative_to(ROOT))
                except ValueError:
                    display_path = str(output_path)
                outcome = GenerationOutcome(
                    "succeeded",
                    normalized_question,
                    config=config,
                    output_path=display_path,
                )
        except (ProviderError, ValueError, ModelValidationError, RuntimeError, OSError) as error:
            outcome = GenerationOutcome("manual_required", normalized_question, str(error))

        if outcome.status == "manual_required":
            self.recorder.append(
                {
                    "request_id": request_id,
                    "event": "generation_fallback",
                    "question": normalized_question,
                    "reason": outcome.reason,
                    "status": "awaiting_contact",
                }
            )
        return outcome


class GenerationManager:
    def __init__(self, service: GenerationService, runtime_dir: Path, max_workers: int = 2) -> None:
        self.service = service
        self.runtime_dir = runtime_dir
        self.executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="courseware-generator")
        self.jobs: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def submit(self, question: object) -> dict[str, Any]:
        normalized_question = normalize_question(question)
        job_id = uuid.uuid4().hex[:12]
        now = datetime.now(timezone.utc).isoformat()
        job = {
            "id": job_id,
            "status": "queued",
            "question": normalized_question,
            "created_at": now,
            "updated_at": now,
        }
        with self._lock:
            self.jobs[job_id] = job
        self.executor.submit(self._run, job_id, normalized_question)
        return dict(job)

    def _run(self, job_id: str, question: str) -> None:
        self._update(job_id, status="running")
        output_dir = self.runtime_dir / "generated" / job_id
        outcome = self.service.generate_sync(question, output_dir, request_id=job_id)
        if outcome.status == "succeeded":
            self._update(
                job_id,
                status="succeeded",
                output_url=f"/generated/{job_id}/",
                config=outcome.config,
            )
        else:
            self._update(job_id, status="manual_required", reason=outcome.reason)

    def _update(self, job_id: str, **changes: Any) -> None:
        with self._lock:
            job = self.jobs[job_id]
            job.update(changes)
            job["updated_at"] = datetime.now(timezone.utc).isoformat()

    def get(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            job = self.jobs.get(job_id)
            return dict(job) if job else None

    def record_contact(self, job_id: str, name: object, contact: object, note: object = "") -> None:
        job = self.get(job_id)
        if not job or job["status"] != "manual_required":
            raise ValueError("找不到需要人工处理的生成任务")
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 50:
            raise ValueError("请填写称呼")
        if not isinstance(contact, str) or not 3 <= len(contact.strip()) <= 120:
            raise ValueError("请填写有效联系方式")
        if not isinstance(note, str) or len(note) > 500:
            raise ValueError("补充说明不能超过 500 字")
        self.service.recorder.append(
            {
                "request_id": job_id,
                "event": "contact_submitted",
                "question": job["question"],
                "name": name.strip(),
                "contact": contact.strip(),
                "note": note.strip(),
                "status": "pending_manual_delivery",
            }
        )

    def close(self) -> None:
        self.executor.shutdown(wait=True, cancel_futures=False)
