from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "services" / "feedback" / "tools" / "build_teacher_review_dispositions.py"
STORAGE_KEY = "a1" * 32


class BuildTeacherReviewDispositionsTests(unittest.TestCase):
    def test_builds_two_append_only_dispositions_without_printing_token(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "dispositions"
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--output", str(output)],
                cwd=ROOT,
                env={**os.environ, "COURSEWARE_TEACHER_STORAGE_KEY": STORAGE_KEY},
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn(STORAGE_KEY, result.stdout + result.stderr)
            objects = [
                json.loads(path.read_text(encoding="utf-8"))
                for path in sorted((output / f"feedback/reviews/{STORAGE_KEY}").rglob("*.json"))
            ]
            self.assertEqual(len(objects), 2)
            self.assertEqual({item["status"] for item in objects}, {"closed"})
            self.assertEqual(
                {item["revision_id"] for item in objects},
                {"q01-v8-1c89623d5bf0", "5c8590bd2060"},
            )
            self.assertTrue(all(item["record_type"] == "task_disposition" for item in objects))

    def test_refuses_to_overwrite_existing_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "dispositions"
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
