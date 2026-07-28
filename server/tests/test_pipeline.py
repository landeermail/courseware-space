from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


SERVER_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER_DIR))

from generator_service import (  # noqa: E402
    GenerationService,
    ManualRequestRecorder,
    build_template_config,
    parse_ai_response,
)


VALID_PARAMETERS = {
    "magnetic_field_t": 0.5,
    "rod_length_m": 1.0,
    "rod_speed_m_s": 2.0,
    "resistance_ohm": 0.4,
    "field_direction": "into_page",
    "motion_direction": "right",
}


class FixedClient:
    def __init__(self, payload: dict[str, object] | str) -> None:
        self.response = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        return self.response


class PipelineTests(unittest.TestCase):
    def test_strict_response_accepts_exact_schema(self) -> None:
        supported, reason, parameters = parse_ai_response(
            json.dumps({"supported": True, "reason": "", "parameters": VALID_PARAMETERS})
        )
        self.assertTrue(supported)
        self.assertEqual(reason, "")
        self.assertEqual(parameters, VALID_PARAMETERS)

    def test_strict_response_rejects_extra_executable_field(self) -> None:
        parameters = {**VALID_PARAMETERS, "physics_code": "E = custom()"}
        with self.assertRaisesRegex(ValueError, "白名单"):
            parse_ai_response(json.dumps({"supported": True, "reason": "", "parameters": parameters}))

    def test_scope_rejection_requires_null_parameters(self) -> None:
        with self.assertRaisesRegex(ValueError, "必须为 null"):
            parse_ai_response(
                json.dumps({"supported": False, "reason": "旋转导体", "parameters": VALID_PARAMETERS})
            )

    def test_template_rejects_negative_resistance(self) -> None:
        with self.assertRaisesRegex(ValueError, "超出模板范围"):
            build_template_config(
                "闭合平行导轨间距1 m，0.5 T匀强磁场向里，杆以2 m/s向右匀速运动，总电阻0.4 Ω。",
                {**VALID_PARAMETERS, "resistance_ohm": -0.4},
            )

    def test_service_renders_valid_response(self) -> None:
        response = {"supported": True, "reason": "", "parameters": VALID_PARAMETERS}
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            service = GenerationService(FixedClient(response), ManualRequestRecorder(root / "manual.jsonl"))  # type: ignore[arg-type]
            outcome = service.generate_sync(
                "闭合平行导轨间距1 m，0.5 T匀强磁场向里，杆以2 m/s向右匀速运动，总电阻0.4 Ω。",
                root / "output",
            )
            self.assertEqual(outcome.status, "succeeded")
            self.assertTrue((root / "output" / "index.html").is_file())

    def test_service_records_scope_fallback(self) -> None:
        response = {"supported": False, "reason": "旋转导体超出范围", "parameters": None}
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            recorder_path = root / "manual.jsonl"
            service = GenerationService(FixedClient(response), ManualRequestRecorder(recorder_path))  # type: ignore[arg-type]
            outcome = service.generate_sync(
                "长1 m的导体杆在匀强磁场中绕一端匀速转动，求两端的感应电动势。",
                root / "output",
            )
            self.assertEqual(outcome.status, "manual_required")
            record = json.loads(recorder_path.read_text(encoding="utf-8"))
            self.assertEqual(record["status"], "awaiting_contact")


if __name__ == "__main__":
    unittest.main()
