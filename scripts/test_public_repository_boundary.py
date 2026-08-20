from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parent.parent
FORBIDDEN_ROOTS = {
    "BLOCKED.md",
    "CONTEXT.md",
    "PROGRESS.md",
    "docs",
    "production",
    "research",
    "services",
}


class PublicRepositoryBoundaryTests(unittest.TestCase):
    def test_internal_roots_are_absent(self) -> None:
        present = sorted(name for name in FORBIDDEN_ROOTS if (ROOT / name).exists())
        self.assertEqual(present, [])

    def test_public_root_has_an_explicit_rights_notice(self) -> None:
        notice = (ROOT / "LICENSE.md").read_text(encoding="utf-8")
        self.assertIn("All rights reserved", notice)
        self.assertIn("does not grant an open-source license", notice)


if __name__ == "__main__":
    unittest.main()
