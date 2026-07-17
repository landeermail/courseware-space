from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


VALIDATOR = Path(__file__).with_name("validate_site.py")


class ValidatorCliTests(unittest.TestCase):
    def run_validator(self, root: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(VALIDATOR), str(root)],
            check=False,
            capture_output=True,
            text=True,
        )

    def create_site(self, root: Path, lesson_path: str = "lesson/") -> Path:
        courseware_data = {
            "categories": [
                {
                    "lessons": [
                        {
                            "title": "测试主题",
                            "entries": [
                                {"title": "测试入口", "path": lesson_path},
                            ],
                        }
                    ]
                }
            ],
        }
        (root / "index.html").write_text(
            f"<script>const coursewareData = {json.dumps(courseware_data)};</script>",
            encoding="utf-8",
        )
        lesson = root / "lesson"
        lesson.mkdir()
        (lesson / "index.html").write_text("<main>fixture</main>", encoding="utf-8")
        return lesson

    def test_valid_site_passes_through_cli(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            lesson = self.create_site(root)
            (lesson / "image.png").write_bytes(b"fixture")
            (lesson / "icon.svg").write_text("<svg></svg>", encoding="utf-8")
            (lesson / "index.html").write_text(
                '<link rel="manifest" href="manifest.webmanifest">'
                '<img src="image.png"><a href="#details">details</a>'
                '<script src="https://example.com/library.js"></script>',
                encoding="utf-8",
            )
            (lesson / "manifest.webmanifest").write_text(
                json.dumps(
                    {
                        "start_url": "./",
                        "scope": "./",
                        "icons": [{"src": "icon.svg"}],
                    }
                ),
                encoding="utf-8",
            )
            (lesson / "sw.js").write_text(
                'const CORE_ASSETS = ["./", "./index.html", "./image.png"];',
                encoding="utf-8",
            )

            result = self.run_validator(root)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("静态站点校验通过", result.stdout)

    def test_cli_reports_all_missing_and_wrong_case_resources(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            lesson = self.create_site(root)
            (lesson / "Image.png").write_bytes(b"fixture")
            (lesson / "index.html").write_text(
                '<link rel="manifest" href="manifest.webmanifest">'
                '<img src="image.png">',
                encoding="utf-8",
            )
            (lesson / "manifest.webmanifest").write_text(
                json.dumps(
                    {
                        "start_url": "./",
                        "icons": [{"src": "missing-icon.svg"}],
                    }
                ),
                encoding="utf-8",
            )
            (lesson / "sw.js").write_text(
                'const CORE_ASSETS = ["./", "./missing.js"];',
                encoding="utf-8",
            )

            result = self.run_validator(root)

            self.assertEqual(result.returncode, 1)
            self.assertIn("image.png", result.stderr)
            self.assertIn("missing-icon.svg", result.stderr)
            self.assertIn("missing.js", result.stderr)

    def test_cli_rejects_homepage_path_without_trailing_slash(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self.create_site(root, lesson_path="lesson")

            result = self.run_validator(root)

            self.assertEqual(result.returncode, 1)
            self.assertIn("path 必须以 / 结尾", result.stderr)

    def test_cli_rejects_card_without_entries(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            courseware_data = {
                "categories": [{"lessons": [{"title": "空卡片"}]}],
            }
            (root / "index.html").write_text(
                f"<script>const coursewareData = {json.dumps(courseware_data)};</script>",
                encoding="utf-8",
            )

            result = self.run_validator(root)

            self.assertEqual(result.returncode, 1)
            self.assertIn("entries 必须是非空数组", result.stderr)


if __name__ == "__main__":
    unittest.main()
