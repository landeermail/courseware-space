from __future__ import annotations

import json
from pathlib import Path
import unittest

from validate_feedback import DIMENSIONS, validate_feedback


ROOT = Path(__file__).resolve().parent


def valid_payload() -> dict[str, object]:
    return json.loads((ROOT / "example.json").read_text(encoding="utf-8"))


class FeedbackValidationTests(unittest.TestCase):
    def test_valid_feedback_passes(self) -> None:
        self.assertEqual(validate_feedback(valid_payload()), [])

    def test_missing_dimension_is_rejected(self) -> None:
        payload = valid_payload()
        del payload["dimensions"]["exam_connection"]  # type: ignore[index]

        errors = validate_feedback(payload)

        self.assertTrue(any("exam_connection" in error for error in errors), errors)

    def test_failed_dimension_requires_note(self) -> None:
        payload = valid_payload()
        payload["dimensions"]["task_driven"] = {"verdict": "fail", "note": "   "}  # type: ignore[index]

        errors = validate_feedback(payload)

        self.assertTrue(any("task_driven.note" in error for error in errors), errors)

    def test_reject_requires_reason(self) -> None:
        payload = valid_payload()
        payload["overall"] = {"verdict": "reject", "rejection_reasons": [], "note": ""}

        errors = validate_feedback(payload)

        self.assertTrue(any("至少选择一个" in error for error in errors), errors)

    def test_additional_field_is_rejected(self) -> None:
        payload = valid_payload()
        payload["reviewer_name"] = "不应保存"

        errors = validate_feedback(payload)

        self.assertTrue(any("reviewer_name" in error for error in errors), errors)

    def test_date_time_requires_timezone(self) -> None:
        payload = valid_payload()
        payload["reviewed_at"] = "2026-07-30T09:00:00"

        errors = validate_feedback(payload)

        self.assertTrue(any("reviewed_at" in error for error in errors), errors)

    def test_schema_and_validator_dimension_keys_match(self) -> None:
        schema = json.loads((ROOT / "schema.json").read_text(encoding="utf-8"))
        schema_dimensions = tuple(schema["properties"]["dimensions"]["required"])

        self.assertEqual(schema_dimensions, DIMENSIONS)


if __name__ == "__main__":
    unittest.main()
