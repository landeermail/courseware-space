from __future__ import annotations

from pathlib import Path
import subprocess
import unittest


REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
CANONICAL_MODULES = (
    "site",
    "production",
    "services/feedback",
    "research/generation",
)
LEGACY_SOURCE_ROOTS = (
    "deploy",
    "trial",
    "feedback",
    "generator",
    "harness",
    "library",
    "server",
    "templates",
)


class ModuleLayoutTests(unittest.TestCase):
    def test_four_responsibility_modules_exist(self) -> None:
        for relative in CANONICAL_MODULES:
            self.assertTrue((REPOSITORY_ROOT / relative).is_dir(), relative)

    def test_legacy_roots_have_no_tracked_source(self) -> None:
        if not (REPOSITORY_ROOT / ".git").exists():
            self.skipTest("tracked-source assertion requires a Git checkout")

        result = subprocess.run(
            ["git", "ls-files", "--", *LEGACY_SOURCE_ROOTS],
            cwd=REPOSITORY_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        tracked_existing = [
            path
            for path in result.stdout.splitlines()
            if (REPOSITORY_ROOT / path).exists()
        ]
        self.assertEqual(tracked_existing, [])

    def test_current_entry_docs_name_the_canonical_modules(self) -> None:
        for document in ("AGENTS.md", "README.md", "CONTEXT.md"):
            source = (REPOSITORY_ROOT / document).read_text(encoding="utf-8")
            with self.subTest(document=document):
                for relative in CANONICAL_MODULES:
                    self.assertIn(f"`{relative}", source)


if __name__ == "__main__":
    unittest.main()
