from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


VALIDATOR = Path(__file__).with_name("validate_site.py")
SHOWCASE_URL = "https://github.com/landeermail/courseware-space#readme"


class ValidatorCliTests(unittest.TestCase):
    def run_validator(self, root: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(VALIDATOR), str(root)],
            check=False,
            capture_output=True,
            text=True,
        )

    def create_site(self, root: Path) -> Path:
        (root / "index.html").write_text(
            f'<meta http-equiv="refresh" content="0; url={SHOWCASE_URL}">'
            f'<a href="{SHOWCASE_URL}">查看产品介绍</a>',
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

    def test_cli_rejects_wrong_root_redirect(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self.create_site(root)
            (root / "index.html").write_text(
                '<meta http-equiv="refresh" content="0; url=https://example.com/">'
                '<a href="https://example.com/">错误入口</a>',
                encoding="utf-8",
            )

            result = self.run_validator(root)

            self.assertEqual(result.returncode, 1)
            self.assertIn("必须立即跳转到公开仓库 README", result.stderr)
            self.assertIn("缺少指向公开仓库 README", result.stderr)

    def test_cli_rejects_missing_fallback_link(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "index.html").write_text(
                f'<meta http-equiv="refresh" content="0; url={SHOWCASE_URL}">',
                encoding="utf-8",
            )

            result = self.run_validator(root)

            self.assertEqual(result.returncode, 1)
            self.assertIn("缺少指向公开仓库 README", result.stderr)


if __name__ == "__main__":
    unittest.main()
