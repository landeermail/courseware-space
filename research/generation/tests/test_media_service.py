from __future__ import annotations

import base64
import json
import sys
import tempfile
import unittest
from pathlib import Path


SERVER_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER_DIR))

from research.generation.runtime.generator_service import GenerationManager, GenerationService, ManualRequestRecorder  # noqa: E402
from research.generation.runtime.media_service import MediaConfirmationWorkflow, MediaError, MediaParser, decode_upload  # noqa: E402


VALID_PARAMETERS = {
    "magnetic_field_t": 0.5,
    "rod_length_m": 1.0,
    "rod_speed_m_s": 2.0,
    "resistance_ohm": 0.4,
    "field_direction": "into_page",
    "motion_direction": "right",
}


def response(
    *,
    confidence: float = 0.95,
    supported: bool = True,
    parameters: dict[str, object] | None = None,
    current_direction: str | None = "d_to_c",
    count: int = 1,
) -> str:
    questions = []
    for index in range(count):
        questions.append(
            {
                "question_text": f"闭合平行导轨间距1 m，0.5 T匀强磁场向里，杆以2 m/s向右匀速运动，总电阻0.4 Ω，求第{index + 1}问电动势。",
                "confidence": confidence,
                "supported": supported,
                "reason": "" if supported else "超出当前模板范围",
                "parameters": parameters if parameters is not None else VALID_PARAMETERS,
                "current_direction": current_direction,
                "asks": ["求感应电动势"],
            }
        )
    return json.dumps({"questions": questions}, ensure_ascii=False)


class VisionClient:
    configured = True

    def __init__(self, payload: str) -> None:
        self.payload = payload
        self.calls = 0

    def complete_vision(self, system_prompt: str, user_prompt: str, mime_type: str, image: bytes) -> str:
        self.calls += 1
        return self.payload

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        raise AssertionError("确认后的图片/PDF 流程不应重新调用文本解析")


class MediaWorkflowTests(unittest.TestCase):
    def test_upload_rejects_declared_type_mismatch(self) -> None:
        encoded = base64.b64encode(b"not an image").decode("ascii")
        with self.assertRaisesRegex(MediaError, "声明类型"):
            decode_upload("question.png", "image/png", encoded)

    def test_one_page_can_split_multiple_questions(self) -> None:
        parser = MediaParser(VisionClient(response(count=2)))  # type: ignore[arg-type]
        result = parser.parse("questions.png", "image/png", self._png())
        self.assertEqual([item["id"] for item in result["questions"]], ["p1-q1", "p1-q2"])
        self.assertEqual(result["status"], "awaiting_confirmation")

    def test_low_confidence_requires_input_instead_of_guessing(self) -> None:
        parser = MediaParser(VisionClient(response(confidence=0.4)))  # type: ignore[arg-type]
        result = parser.parse("blur.png", "image/png", self._png())
        self.assertEqual(result["status"], "needs_input")
        self.assertFalse(result["questions"][0]["ready_for_confirmation"])
        self.assertIn("补述", result["message"])

    def test_unreadable_model_response_becomes_safe_supplement_prompt(self) -> None:
        parser = MediaParser(VisionClient("not-json"))  # type: ignore[arg-type]
        result = parser.parse("unreadable.png", "image/png", self._png())
        self.assertEqual(result["status"], "needs_input")
        self.assertEqual(result["questions"][0]["confidence"], 0.0)
        self.assertFalse(result["questions"][0]["supported"])
        self.assertIn("补述", result["questions"][0]["question_text"])

    def test_generation_manager_rejects_forged_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            client = VisionClient(response())
            manager = GenerationManager(
                GenerationService(client, ManualRequestRecorder(root / "manual.jsonl")),  # type: ignore[arg-type]
                root,
            )
            with self.assertRaisesRegex(ValueError, "确认闸"):
                manager.submit_confirmed(
                    confirmation_id="a" * 24,
                    question="闭合导轨中导体杆向右匀速切割磁感线，已知完整参数并求电动势。",
                    parameters=VALID_PARAMETERS,
                    source_input_type="image",
                    asks=["求电动势"],
                )
            manager.close()

    def test_teacher_flag_is_a_hard_gate(self) -> None:
        with self._workflow(response()) as (workflow, _manager, _root):
            parsed = workflow.parse_upload("question.png", "image/png", self._png())
            payload = self._confirmation(parsed)
            payload["teacher_confirmed"] = False
            with self.assertRaisesRegex(MediaError, "显式确认"):
                workflow.confirm_and_submit(payload)

    def test_teacher_correction_overrides_reversed_field(self) -> None:
        with self._workflow(response()) as (workflow, manager, root):
            parsed = workflow.parse_upload("question.png", "image/png", self._png())
            payload = self._confirmation(parsed)
            payload["parameters"] = {**VALID_PARAMETERS, "field_direction": "out_of_page"}
            payload["current_direction"] = "c_to_d"
            result = workflow.confirm_and_submit(payload)
            self.assertTrue(result["corrections_applied"])
            job_id = result["job"]["id"]
            manager.close()
            job = manager.get(job_id)
            self.assertEqual(job["status"], "succeeded")
            self.assertEqual(job["config"]["field_direction"], "out_of_page")
            self.assertTrue((root / "generated" / job_id / "metadata.json").is_file())

    def test_inconsistent_current_direction_is_rejected(self) -> None:
        with self._workflow(response()) as (workflow, _manager, _root):
            parsed = workflow.parse_upload("question.png", "image/png", self._png())
            payload = self._confirmation(parsed)
            payload["current_direction"] = "c_to_d"
            with self.assertRaisesRegex(MediaError, "不一致"):
                workflow.confirm_and_submit(payload)

    def _confirmation(self, parsed: dict[str, object]) -> dict[str, object]:
        question = parsed["questions"][0]  # type: ignore[index]
        return {
            "parse_id": parsed["id"],
            "question_id": question["id"],
            "teacher_confirmed": True,
            "question_text": question["question_text"],
            "parameters": question["parameters"],
            "current_direction": question["current_direction"],
            "asks": question["asks"],
        }

    def _workflow(self, payload: str):
        class Context:
            def __enter__(inner_self):
                inner_self.temp = tempfile.TemporaryDirectory()
                root = Path(inner_self.temp.name)
                client = VisionClient(payload)
                manager = GenerationManager(
                    GenerationService(client, ManualRequestRecorder(root / "manual.jsonl")),  # type: ignore[arg-type]
                    root,
                )
                inner_self.manager = manager
                return MediaConfirmationWorkflow(MediaParser(client), manager), manager, root  # type: ignore[arg-type]

            def __exit__(inner_self, exc_type, exc, traceback):
                inner_self.manager.close()
                inner_self.temp.cleanup()

        return Context()

    @staticmethod
    def _png() -> str:
        return base64.b64encode(b"\x89PNG\r\n\x1a\nminimal-test-data").decode("ascii")


if __name__ == "__main__":
    unittest.main()
