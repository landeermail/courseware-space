from __future__ import annotations

import hashlib
from pathlib import Path
import tempfile
import unittest

from build_pages import (
    EXPECTED_TOP_LEVEL,
    PUBLIC_PATHS,
    PagesBuildError,
    artifact_files,
    build_pages,
    validate_pages_boundary,
)


REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
TEACHER_ROOT = Path("preview/TNlUdPGF-r2ZDQ4ZDFWYHS8ERlIxaUJT")
REQUIRED_URLS = (
    Path("index.html"),
    TEACHER_ROOT / "index.html",
    TEACHER_ROOT / "feedback/index.html",
    TEACHER_ROOT / "reviews/index.html",
    TEACHER_ROOT / "q01-v8-1c89623d5bf0/index.html",
    TEACHER_ROOT / "q01-vertical-circle/index.html",
    TEACHER_ROOT / "q07-v4-5bb63ec7f581/index.html",
    Path("electromagnetism/q6-plane/index.html"),
    Path("mh370-physics/mh370-physics/index.html"),
    Path("electromagnetism/q13-helicopter-physics/index.html"),
    Path("helicopter-dynamics/q13-helicopter/index.html"),
    Path("electromagnetism/q20-rotating-rod/index.html"),
    Path("electromagnetism/q21-variable-field-rod/index.html"),
    Path("electromagnetism/q21-variable-field-rod-3d/index.html"),
    Path("mechanics/q23-falling-tube-ball/index.html"),
)
INTERNAL_TOP_LEVEL = {
    ".git",
    ".github",
    "deploy",
    "docs",
    "feedback",
    "generator",
    "harness",
    "library",
    "scripts",
    "server",
    "templates",
    "trial",
}


def content_manifest(root: Path) -> dict[str, str]:
    return {
        path.as_posix(): hashlib.sha256((root / path).read_bytes()).hexdigest()
        for path in sorted(artifact_files(root))
    }


class BuildPagesTests(unittest.TestCase):
    def test_build_is_complete_deterministic_and_excludes_internal_roots(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            base = Path(temporary_directory)
            first = base / "first"
            second = base / "second"

            build_pages(REPOSITORY_ROOT, first)
            build_pages(REPOSITORY_ROOT, second)

            self.assertEqual(content_manifest(first), content_manifest(second))
            self.assertEqual({path.name for path in first.iterdir()}, EXPECTED_TOP_LEVEL)
            self.assertFalse(INTERNAL_TOP_LEVEL.intersection(path.name for path in first.iterdir()))
            for required in REQUIRED_URLS:
                self.assertTrue((first / required).is_file(), required.as_posix())

    def test_allowlist_does_not_include_generator_or_internal_roots(self) -> None:
        allowed = {path.as_posix() for path in PUBLIC_PATHS}

        self.assertTrue((REPOSITORY_ROOT / "generator/index.html").is_file())
        self.assertNotIn("generator", allowed)
        self.assertFalse(INTERNAL_TOP_LEVEL.intersection(EXPECTED_TOP_LEVEL))

    def test_pages_workflow_builds_and_uploads_only_the_artifact(self) -> None:
        workflow = (REPOSITORY_ROOT / ".github/workflows/deploy.yml").read_text(
            encoding="utf-8"
        )

        self.assertIn("python3 scripts/build_pages.py --output _site", workflow)
        self.assertRegex(workflow, r"(?m)^\s+path: _site$")
        self.assertNotRegex(workflow, r"(?m)^\s+path: \.$")

    def test_boundary_rejects_unexpected_top_level_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            for name in EXPECTED_TOP_LEVEL:
                path = root / name
                if name in {".nojekyll", "index.html"}:
                    path.write_text("fixture", encoding="utf-8")
                else:
                    path.mkdir()
            (root / "server").mkdir()

            with self.assertRaisesRegex(PagesBuildError, "非白名单顶层路径"):
                validate_pages_boundary(root)


if __name__ == "__main__":
    unittest.main()
