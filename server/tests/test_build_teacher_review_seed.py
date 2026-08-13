from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "build_teacher_review_seed.py"
TOKEN = "a1" * 24


class BuildTeacherReviewSeedTests(unittest.TestCase):
    def test_builds_three_tasks_and_migrates_q01_v7_without_printing_token(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "seed"
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--output", str(output)],
                cwd=ROOT,
                env={**os.environ, "COURSEWARE_TEACHER_TOKEN": TOKEN},
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn(TOKEN, result.stdout + result.stderr)
            teacher_key = hashlib.sha256(TOKEN.encode("ascii")).hexdigest()
            task_dir = output / f"feedback/tasks/{teacher_key}"
            review_dir = output / f"feedback/reviews/{teacher_key}/q01-v7-teacher-review"
            tasks = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(task_dir.glob("*.json"))]
            reviews = [json.loads(path.read_text(encoding="utf-8")) for path in review_dir.glob("*.json")]

            self.assertEqual(len(tasks), 3)
            self.assertEqual(
                {task["revision_id"] for task in tasks},
                {"q01-v7", "q01-v8-1c89623d5bf0", "5c8590bd2060"},
            )
            self.assertEqual(len(reviews), 1)
            self.assertEqual(reviews[0]["revision_id"], "q01-v7")
            self.assertEqual(reviews[0]["feedback_id"], "feedback-7d414bc2-eb02-4159-bdc9-2f9fec6e956e")
            self.assertIsNone(reviews[0]["previous_feedback_id"])

    def test_refuses_to_overwrite_existing_seed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "seed"
            env = {**os.environ, "COURSEWARE_TEACHER_TOKEN": TOKEN}
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
