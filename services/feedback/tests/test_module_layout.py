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

    def test_local_generation_host_uses_feedback_module_explicitly(self) -> None:
        source = (ROOT / "server" / "app.py").read_text(encoding="utf-8")
        self.assertIn("from services.feedback.access_control import", source)
        self.assertIn("from services.feedback.service import", source)


if __name__ == "__main__":
    unittest.main()
