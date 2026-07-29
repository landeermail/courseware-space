from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server"))

from harness.confirmation import ConfirmationError  # noqa: E402
from harness_service import HarnessService  # noqa: E402


class NoCallClient:
    def complete(self, system_prompt: str, user_prompt: str, **kwargs: object) -> str:
        raise AssertionError("该测试不应调用模型")


class HarnessServiceTests(unittest.TestCase):
    def test_server_gate_requires_explicit_teacher_confirmation(self) -> None:
        service = HarnessService(NoCallClient())
        scenario = {
            "mode": "horizontal",
            "g_m_s2": 10,
            "mass_kg": 1,
            "x0_m": 0,
            "y0_m": 20,
            "speed_m_s": 10,
            "angle_deg": 0,
        }
        with self.assertRaises(ConfirmationError):
            service.confirm("projectile", scenario, False)

    def test_server_gate_returns_token_only_after_normalization(self) -> None:
        service = HarnessService(NoCallClient())
        scenario = {
            "mode": "horizontal",
            "g_m_s2": 10,
            "mass_kg": 1,
            "x0_m": 0,
            "y0_m": 20,
            "speed_m_s": 10,
            "angle_deg": 0,
        }
        self.assertGreater(len(service.confirm("projectile", scenario, True)), 20)

    def test_unknown_domain_is_rejected_before_confirmation(self) -> None:
        service = HarnessService(NoCallClient())
        with self.assertRaisesRegex(ValueError, "projectile"):
            service.confirm("unknown", {}, True)
