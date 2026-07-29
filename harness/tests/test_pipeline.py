from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from harness.confirmation import ConfirmationError, TeacherConfirmationGate
from harness.pipeline import HarnessGenerationError, HarnessPipeline
from harness.tests.test_assertions import PROJECTILE
from harness.tests.test_sandbox import CORRECT_PROJECTILE_JS


HTML = """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>抛体时空实验室</title><style>body{font-family:sans-serif;margin:0;padding:24px}button,input{min-height:44px}.lab{display:grid;gap:16px}.scene{min-height:240px;background:#eef4ff}.readout{font-size:18px}@media(max-width:600px){body{padding:12px}}</style></head><body><main class="lab"><h1>抛体时空实验室</h1><p>操控初速度与角度，观察速度分解、能量和关键时刻。</p><div><label>速度<input data-control id="speed" type="range" min="1" max="50"></label><label>角度<input data-control id="angle" type="range" min="1" max="80"></label></div><div class="scene" aria-label="抛体运动场景"></div><div data-readout class="readout"></div><div data-physical-time>0.00 s（物理时间）</div><div data-demo-time>0.50×（演示倍率）</div><button data-replay>重新观察</button></main><!--HARNESS_PRIMITIVES--><!--HARNESS_MODEL--><!--HARNESS_INPUT--><script>const locked=globalThis.__HARNESS_INPUT__;const initial=coursewareModel.sample(locked);const readout=document.querySelector('[data-readout]');const timeline=CoursewarePrimitives.createTimeline({durationPhysicalS:initial.events.flight_time_s,onChange(state){document.querySelector('[data-physical-time]').textContent=CoursewarePrimitives.formatPhysicalTime(state.physicalTimeS);document.querySelector('[data-demo-time]').textContent=CoursewarePrimitives.formatDemoRate(state.demoRate);readout.textContent='状态点 '+initial.states.length;}});document.querySelector('[data-replay]').addEventListener('click',()=>timeline.replay());document.querySelectorAll('[data-control]').forEach(control=>control.addEventListener('input',()=>{const scenario={...locked.scenario,speed_m_s:Number(document.querySelector('#speed').value||locked.scenario.speed_m_s),angle_deg:Number(document.querySelector('#angle').value||locked.scenario.angle_deg)};coursewareModel.sample({...locked,scenario});}));</script></body></html>"""


def model_artifact(model_js: str) -> str:
    return json.dumps(
        {
            "title": "抛体时空实验室",
            "domain": "projectile",
            "model_js": model_js,
        },
        ensure_ascii=False,
    )


def view_artifact() -> str:
    return json.dumps(
        {
            "teaching_intent": "让学生操控初速度与角度，观察速度分解、机械能和顶点落地点之间的因果联系。",
            "html": HTML,
        },
        ensure_ascii=False,
    )


class FakeClient:
    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self.calls = 0
        self.call_contexts: list[dict[str, object]] = []

    def complete(self, system_prompt: str, user_prompt: str, **kwargs: object) -> str:
        self.call_contexts.append(dict(kwargs))
        response = self.responses[self.calls]
        self.calls += 1
        return response


class UnavailableClient:
    def __init__(self) -> None:
        self.calls = 0

    def complete(self, system_prompt: str, user_prompt: str, **kwargs: object) -> str:
        self.calls += 1
        error = RuntimeError("额度暂不可用")
        error.kind = "quota"
        raise error


class LengthLimitedClient:
    def __init__(self) -> None:
        self.calls = 0

    def complete(self, system_prompt: str, user_prompt: str, **kwargs: object) -> str:
        self.calls += 1
        error = RuntimeError("Kimi 输出达到长度上限，拒绝自动重试")
        error.kind = "length_limit"
        error.metadata = {"finish_reason": "length", "usage": {"completion_tokens": 32768}}
        raise error


class PipelineTests(unittest.TestCase):
    def test_failed_assertion_is_fed_back_and_retry_turns_green(self) -> None:
        wrong = CORRECT_PROJECTILE_JS.replace("mechanical_j:energy", "mechanical_j:1")
        client = FakeClient([model_artifact(wrong), model_artifact(CORRECT_PROJECTILE_JS), view_artifact()])
        gate = TeacherConfirmationGate()
        token = gate.confirm("projectile", PROJECTILE, True)
        with tempfile.TemporaryDirectory() as directory:
            result = HarnessPipeline(client, gate).generate(
                artifact_id="retry-red-green",
                domain="projectile",
                question="以20 m/s、30°斜向上抛出小球，观察其速度、能量、顶点和射程。",
                scenario=PROJECTILE,
                confirmation_token=token,
                output_dir=Path(directory),
            )
            self.assertEqual(result.status, "succeeded")
            self.assertEqual(result.attempts, 3)
            self.assertTrue((Path(directory) / "index.html").is_file())
            first = json.loads((Path(directory) / "model-attempts" / "01.json").read_text())
            second = json.loads((Path(directory) / "model-attempts" / "02.json").read_text())
            view = json.loads((Path(directory) / "view-attempts" / "01.json").read_text())
            self.assertEqual(first["status"], "rejected")
            self.assertEqual(second["status"], "passed")
            self.assertEqual(view["status"], "passed")
            self.assertTrue(all(context["artifact_id"] == "retry-red-green" for context in client.call_contexts))
            self.assertTrue(all(context["prompt_version"] for context in client.call_contexts))

    def test_pipeline_rejects_forged_confirmation_token(self) -> None:
        pipeline = HarnessPipeline(FakeClient([model_artifact(CORRECT_PROJECTILE_JS), view_artifact()]), TeacherConfirmationGate())
        with tempfile.TemporaryDirectory() as directory, self.assertRaises(ConfirmationError):
            pipeline.generate(
                artifact_id="forged",
                domain="projectile",
                question="以20 m/s、30°斜向上抛出小球，观察运动过程和能量变化。",
                scenario=PROJECTILE,
                confirmation_token="forged",
                output_dir=Path(directory),
            )

    def test_provider_outage_is_not_mislabeled_as_physics_rejection(self) -> None:
        gate = TeacherConfirmationGate()
        token = gate.confirm("projectile", PROJECTILE, True)
        client = UnavailableClient()
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(HarnessGenerationError) as captured:
                HarnessPipeline(client, gate).generate(
                    artifact_id="provider-limited",
                    domain="projectile",
                    question="以20 m/s、30°斜向上抛出小球，观察运动过程和能量变化。",
                    scenario=PROJECTILE,
                    confirmation_token=token,
                    output_dir=Path(directory),
                )
            self.assertEqual(captured.exception.kind, "provider_unavailable")
            self.assertEqual(client.calls, 1)
            failure = json.loads((Path(directory) / "failure.json").read_text())
            attempt = json.loads((Path(directory) / "model-attempts" / "01.json").read_text())
            self.assertEqual(failure["status"], "provider_unavailable")
            self.assertEqual(failure["attempts"], 1)
            self.assertEqual(attempt["failure_kind"], "quota")

    def test_length_limit_stops_without_retry_and_preserves_metadata(self) -> None:
        gate = TeacherConfirmationGate()
        token = gate.confirm("projectile", PROJECTILE, True)
        client = LengthLimitedClient()
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(HarnessGenerationError) as captured:
                HarnessPipeline(client, gate).generate(
                    artifact_id="output-limited",
                    domain="projectile",
                    question="以20 m/s、30°斜向上抛出小球，观察运动过程和能量变化。",
                    scenario=PROJECTILE,
                    confirmation_token=token,
                    output_dir=Path(directory),
                )
            self.assertEqual(captured.exception.kind, "output_limited")
            self.assertEqual(client.calls, 1)
            attempt = json.loads((Path(directory) / "model-attempts" / "01.json").read_text())
            failure = json.loads((Path(directory) / "failure.json").read_text())
            self.assertEqual(attempt["provider"]["finish_reason"], "length")
            self.assertEqual(failure["status"], "output_limited")
