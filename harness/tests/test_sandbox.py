from __future__ import annotations

import unittest
from pathlib import Path

from harness.assertions import AssertionFailure
from harness.domains.circular import circular_probe_inputs, validate_circular
from harness.domains.projectile import projectile_input, validate_projectile
from harness.sandbox import SandboxError, execute_model, validate_in_sandbox
from harness.tests.test_assertions import PROJECTILE


CORRECT_PROJECTILE_JS = r"""
globalThis.coursewareModel = Object.freeze({
  sample(input) {
    const s = input.scenario;
    const angle = s.angle_deg * Math.PI / 180;
    const vx0 = s.speed_m_s * Math.cos(angle);
    const vy0 = s.speed_m_s * Math.sin(angle);
    const energy = 0.5 * s.mass_kg * s.speed_m_s ** 2 + s.mass_kg * s.g_m_s2 * s.y0_m;
    const states = input.times_s.map(t => {
      const rawY = s.y0_m + vy0 * t - 0.5 * s.g_m_s2 * t * t;
      const y = Math.max(0, rawY);
      const vy = vy0 - s.g_m_s2 * t;
      const kinetic = 0.5 * s.mass_kg * (vx0 ** 2 + vy ** 2);
      const potential = s.mass_kg * s.g_m_s2 * y;
      return {t_s:t,x_m:s.x0_m+vx0*t,y_m:y,vx_m_s:vx0,vy_m_s:vy,ax_m_s2:0,ay_m_s2:-s.g_m_s2,kinetic_j:kinetic,potential_j:potential,mechanical_j:energy};
    });
    const flight = (vy0 + Math.sqrt(vy0 ** 2 + 2 * s.g_m_s2 * s.y0_m)) / s.g_m_s2;
    const apex = Math.max(0, vy0 / s.g_m_s2);
    return {states,events:{flight_time_s:flight,range_m:vx0*flight,apex_time_s:apex,max_height_m:s.y0_m+vy0**2/(2*s.g_m_s2),optimal_equal_height_angle_deg:45}};
  }
});
"""

ROOT = Path(__file__).resolve().parents[2]
CIRCULAR_REFERENCE_JS = (ROOT / "harness" / "reference" / "circular_model.js").read_text(encoding="utf-8")


class SandboxTests(unittest.TestCase):
    def test_ordinary_function_is_allowed_but_dynamic_function_is_blocked(self) -> None:
        ordinary = "globalThis.coursewareModel={sample:function(input){return {value:input.value}}}"
        self.assertEqual(execute_model(ordinary, {"value": 3}), {"value": 3})
        with self.assertRaises(SandboxError):
            execute_model("globalThis.coursewareModel={sample:new Function('return 1')}", {})
        with self.assertRaises(SandboxError):
            execute_model("globalThis.coursewareModel={sample:Function('return 1')}", {})

    def test_randomness_and_clock_are_blocked_for_reproducibility(self) -> None:
        for capability in ("Math.random()", "Date.now()", "performance.now()"):
            code = "globalThis.coursewareModel={sample(){return {value:" + capability + "}}}"
            with self.subTest(capability=capability), self.assertRaises(SandboxError):
                execute_model(code, {})

    def test_correct_generated_model_turns_green(self) -> None:
        _, report = validate_in_sandbox(CORRECT_PROJECTILE_JS, projectile_input(PROJECTILE), validate_projectile)
        self.assertTrue(report.passed)

    def test_reference_circular_javascript_passes_every_fixture_and_probe(self) -> None:
        import json

        cases = json.loads((ROOT / "harness" / "fixtures" / "circular.json").read_text(encoding="utf-8"))
        for case in cases:
            for probe in circular_probe_inputs(case["scenario"]):
                with self.subTest(case=case["id"], samples=len(probe["angles_rad"])):
                    _, report = validate_in_sandbox(CIRCULAR_REFERENCE_JS, probe, validate_circular)
                    self.assertTrue(report.passed, report.as_dict())

    def test_wrong_generated_physics_is_blocked_red(self) -> None:
        wrong = CORRECT_PROJECTILE_JS.replace("vy_m_s:vy", "vy_m_s:-vy")
        with self.assertRaises(AssertionFailure):
            validate_in_sandbox(wrong, projectile_input(PROJECTILE), validate_projectile)

    def test_node_process_and_infinite_loop_are_blocked(self) -> None:
        with self.assertRaises(SandboxError):
            execute_model("globalThis.coursewareModel={sample(){return process.env}}", {})
        with self.assertRaises(SandboxError):
            execute_model("globalThis.coursewareModel={sample(){while(true){} }}", {}, timeout=1)
