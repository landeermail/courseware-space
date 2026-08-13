from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
MODULE = ROOT / "services" / "feedback"


class FeedbackModuleLayoutTests(unittest.TestCase):
    def test_feedback_runtime_has_one_source_owner(self) -> None:
        for path in (
            MODULE / "app.py",
            MODULE / "access_control.py",
            MODULE / "service.py",
            MODULE / "review_workspace.py",
            MODULE / "schema" / "validate_feedback.py",
            MODULE / "deploy" / "build_package.sh",
            MODULE / "deploy" / "deploy.sh",
        ):
            self.assertTrue(path.is_file(), path)

        for obsolete in (
            ROOT / "feedback",
            ROOT / "server" / "feedback_app.py",
            ROOT / "server" / "feedback_service.py",
            ROOT / "server" / "review_workspace.py",
            ROOT / "deploy" / "build_feedback_package.sh",
            ROOT / "deploy" / "deploy_feedback_only.sh",
        ):
            self.assertFalse(obsolete.exists(), obsolete)

    def test_generation_is_not_a_feedback_runtime_caller(self) -> None:
        generation = ROOT / "research" / "generation"
        self.assertTrue((generation / "app.py").is_file())
        for base in (generation / "app.py", generation / "runtime"):
            paths = [base] if base.is_file() else base.glob("*.py")
            for path in paths:
                source = path.read_text(encoding="utf-8")
                self.assertNotIn("services.feedback", source, path)
                self.assertNotIn("feedback_service", source, path)


if __name__ == "__main__":
    unittest.main()
