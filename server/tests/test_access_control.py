from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


SERVER_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER_DIR))

from access_control import AccessCodeGate  # noqa: E402


class AccessCodeGateTests(unittest.TestCase):
    def test_enabled_gate_accepts_only_exact_code(self) -> None:
        gate = AccessCodeGate("correct-horse-battery-staple")

        self.assertTrue(gate.required)
        self.assertTrue(gate.allows("correct-horse-battery-staple"))
        self.assertFalse(gate.allows("correct-horse-battery-staplE"))
        self.assertFalse(gate.allows(None))

    def test_local_environment_can_leave_gate_disabled(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            gate = AccessCodeGate.from_environment()

        self.assertFalse(gate.required)
        self.assertTrue(gate.allows(None))

    def test_cloud_environment_fails_closed_without_code(self) -> None:
        with patch.dict(os.environ, {"COURSEWARE_CLOUD_MODE": "1"}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "必须设置"):
                AccessCodeGate.from_environment()

    def test_environment_rejects_ambiguous_whitespace(self) -> None:
        with patch.dict(os.environ, {"COURSEWARE_ACCESS_CODE": " secret "}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "空白"):
                AccessCodeGate.from_environment()


if __name__ == "__main__":
    unittest.main()
