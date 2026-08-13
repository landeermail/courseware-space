from __future__ import annotations

import unittest

from research.generation.harness.confirmation import ConfirmationError, TeacherConfirmationGate


class ConfirmationGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.gate = TeacherConfirmationGate()
        self.scenario = {"speed_m_s": 20.0, "angle_deg": 45.0}

    def test_explicit_confirmation_is_required(self) -> None:
        with self.assertRaises(ConfirmationError):
            self.gate.confirm("projectile", self.scenario, False)

    def test_token_is_bound_to_domain_and_parameters_and_is_single_use(self) -> None:
        token = self.gate.confirm("projectile", self.scenario, True)
        with self.assertRaises(ConfirmationError):
            self.gate.consume(token, "projectile", {**self.scenario, "angle_deg": 30.0})
        token = self.gate.confirm("projectile", self.scenario, True)
        self.gate.consume(token, "projectile", self.scenario)
        with self.assertRaises(ConfirmationError):
            self.gate.consume(token, "projectile", self.scenario)

    def test_token_expires_and_cannot_be_reused(self) -> None:
        now = [100.0]
        gate = TeacherConfirmationGate(ttl_seconds=10.0, clock=lambda: now[0])
        token = gate.confirm("projectile", self.scenario, True)
        now[0] = 111.0
        with self.assertRaisesRegex(ConfirmationError, "过期"):
            gate.consume(token, "projectile", self.scenario)
        with self.assertRaises(ConfirmationError):
            gate.consume(token, "projectile", self.scenario)
