from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


SERVER_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER_DIR))

from access_control import AccessCodeGate  # noqa: E402

STRONG_CODE = "a1" * 24


class AccessCodeGateTests(unittest.TestCase):
    def test_existing_alphanumeric_teacher_link_is_valid(self) -> None:
        code = "Z9" * 24

        gate = AccessCodeGate(code)

        self.assertTrue(gate.allows(code))

    def test_enabled_gate_accepts_only_exact_code(self) -> None:
        gate = AccessCodeGate(STRONG_CODE)

        self.assertTrue(gate.required)
        self.assertTrue(gate.allows(STRONG_CODE))
        self.assertFalse(gate.allows(STRONG_CODE[:-1] + "2"))
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

    def test_environment_rejects_weak_or_noncanonical_code(self) -> None:
        for weak in ("short", "a-" * 24, "a_" * 24, "a1" * 23):
            with self.subTest(weak_length=len(weak)):
                with patch.dict(os.environ, {"COURSEWARE_ACCESS_CODE": weak}, clear=True):
                    with self.assertRaisesRegex(RuntimeError, "48 位"):
                        AccessCodeGate.from_environment()

    def test_environment_accepts_192_bit_hex_code(self) -> None:
        with patch.dict(os.environ, {"COURSEWARE_ACCESS_CODE": STRONG_CODE}, clear=True):
            gate = AccessCodeGate.from_environment()
        self.assertTrue(gate.allows(STRONG_CODE))


if __name__ == "__main__":
    unittest.main()
