from __future__ import annotations

import os
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "deploy" / "deploy.sh"


def deployment_environment(code: str) -> dict[str, str]:
    return {
        **os.environ,
        "ALIBABA_CLOUD_ACCESS_KEY_ID": "test-id",
        "ALIBABA_CLOUD_ACCESS_KEY_SECRET": "test-secret",
        "KIMI_API_KEY": "test-kimi",
        "COURSEWARE_ACCESS_CODE": code,
        "COURSEWARE_OSS_BUCKET": "courseware-space-test",
        "COURSEWARE_FEEDBACK_OSS_BUCKET": "courseware-space-private-test",
        "ALIYUN_CLI": "/definitely/missing/aliyun",
    }


class DeployAccessCodePolicyTests(unittest.TestCase):
    def test_deploy_refuses_weak_code_before_cloud_work(self) -> None:
        result = subprocess.run(
            ["bash", str(SCRIPT)],
            cwd=ROOT,
            env=deployment_environment("weak"),
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("openssl rand -hex 24", result.stderr)
        self.assertNotIn("pip", result.stdout + result.stderr)

    def test_strong_code_passes_policy_and_reaches_next_local_gate(self) -> None:
        result = subprocess.run(
            ["bash", str(SCRIPT)],
            cwd=ROOT,
            env=deployment_environment("a1" * 24),
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("未找到阿里云 CLI", result.stderr)
        self.assertNotIn("openssl rand -hex 24", result.stderr)


if __name__ == "__main__":
    unittest.main()
