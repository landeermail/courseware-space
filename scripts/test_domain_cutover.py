from __future__ import annotations

import subprocess
import sys
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "domain_cutover.py"


class DomainCutoverTests(unittest.TestCase):
    def test_dry_run_lists_complete_plan_without_cloud_changes(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--domain", "example.edu.cn",
                "--icp-number", "浙ICP备00000000号-1",
                "--oss-bucket", "courseware-space-site-123",
                "--fc-function", "courseware-space-generator",
                "--dry-run",
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertIn("mode=dry-run", result.stdout)
        self.assertIn("OSS bucket", result.stdout)
        self.assertIn("FC 函数", result.stdout)
        self.assertIn("iPad 横屏", result.stdout)
        self.assertIn("cloud_changes=0", result.stdout)

    def test_script_refuses_non_dry_run(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--domain", "example.edu.cn",
                "--icp-number", "浙ICP备00000000号-1",
                "--oss-bucket", "courseware-space-site-123",
                "--fc-function", "courseware-space-generator",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("只允许 --dry-run", result.stderr)


if __name__ == "__main__":
    unittest.main()
