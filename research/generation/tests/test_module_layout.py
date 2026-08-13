from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
MODULE = ROOT / "research" / "generation"


class GenerationModuleLayoutTests(unittest.TestCase):
    def test_generation_has_one_source_owner(self) -> None:
        for required in (
            MODULE / "app.py",
            MODULE / "generator" / "index.html",
            MODULE / "runtime" / "kimi_client.py",
            MODULE / "harness" / "pipeline.py",
            MODULE / "templates" / "conducting-rod" / "template.html",
            MODULE / "library" / "catalog.json",
            MODULE / "validate.py",
        ):
            self.assertTrue(required.is_file(), required)

        for obsolete in ("generator", "harness", "library", "server", "templates"):
            self.assertFalse((ROOT / obsolete).exists(), obsolete)

    def test_generation_does_not_import_feedback(self) -> None:
        for base in (MODULE / "app.py", MODULE / "runtime"):
            paths = [base] if base.is_file() else base.glob("*.py")
            for path in paths:
                source = path.read_text(encoding="utf-8")
                self.assertNotIn("services.feedback", source, path)
                self.assertNotIn("feedback_service", source, path)

    def test_direct_entrypoints_resolve_package_from_repository_root(self) -> None:
        for script in (
            MODULE / "app.py",
            MODULE / "harness" / "run_feasibility.py",
            MODULE / "tools" / "run_acceptance.py",
        ):
            result = subprocess.run(
                [sys.executable, str(script), "--help"],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
