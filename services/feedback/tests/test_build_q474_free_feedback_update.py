from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "services" / "feedback" / "tools" / "build_q474_free_feedback_update.py"
STORAGE_KEY = "c3" * 32


class BuildQ474FreeFeedbackUpdateTests(unittest.TestCase):
    def test_builds_task_and_relayed_feedback_without_printing_storage_key(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "q474-feedback"
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--output", str(output)],
                cwd=ROOT,
                env={**os.environ, "COURSEWARE_TEACHER_STORAGE_KEY": STORAGE_KEY},
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn(STORAGE_KEY, result.stdout + result.stderr)
            task = json.loads(
                (output / f"feedback/tasks/{STORAGE_KEY}/q474-v1-teacher-feedback.json").read_text(
                    encoding="utf-8"
                )
            )
            response = json.loads(
                (
                    output
                    / f"feedback/reviews/{STORAGE_KEY}/q474-v1-teacher-feedback/feedback-q474-teacher-relay-20260820.json"
                ).read_text(encoding="utf-8")
            )
            deployment_updates = json.loads(
                (output / "review-updates.json").read_text(encoding="utf-8")
            )

            self.assertEqual(task["feedback_mode"], "freeform")
            self.assertEqual(task["revision_id"], "q474-v1-39e8e4f62f4b")
            self.assertEqual(response["record_type"], "free_feedback")
            self.assertEqual(response["source_channel"], "product_owner_relay")
            self.assertEqual(response["message"], "老师也表示很满意。")
            self.assertIn("474-longitudinal-wave.md", response["source_ref"])
            self.assertEqual(deployment_updates, [{"task": task, "feedback": response}])

    def test_refuses_to_overwrite_existing_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "q474-feedback"
            env = {**os.environ, "COURSEWARE_TEACHER_STORAGE_KEY": STORAGE_KEY}
            first = subprocess.run(
                [sys.executable, str(SCRIPT), "--output", str(output)],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
            )
            second = subprocess.run(
                [sys.executable, str(SCRIPT), "--output", str(output)],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
            )

            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertNotEqual(second.returncode, 0)
            self.assertIn("已存在", second.stderr)


if __name__ == "__main__":
    unittest.main()
