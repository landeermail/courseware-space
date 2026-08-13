from __future__ import annotations

import math
import unittest

from research.generation.harness.assertions import ACCELERATION, LENGTH, TIME, VELOCITY, dimension_check
from research.generation.harness.domains.circular import circular_input, validate_circular
from research.generation.harness.domains.projectile import projectile_input, validate_projectile


PROJECTILE = {
    "mode": "oblique",
    "g_m_s2": 10.0,
    "mass_kg": 2.0,
    "x0_m": 0.0,
    "y0_m": 0.0,
    "speed_m_s": 20.0,
    "angle_deg": 30.0,
}

VERTICAL = {
    "mode": "vertical_string",
    "mass_kg": 1.0,
    "radius_m": 2.0,
    "g_m_s2": 10.0,
    "speed_m_s": 11.0,
    "central_mass_kg": 0.0,
    "G_n_m2_kg2": 6.6743e-11,
}


def projectile_output(scenario: dict[str, float | str]) -> dict[str, object]:
    model_input = projectile_input(scenario)
    angle = math.radians(float(scenario["angle_deg"]))
    speed = float(scenario["speed_m_s"])
    vx0 = speed * math.cos(angle)
    vy0 = speed * math.sin(angle)
    g = float(scenario["g_m_s2"])
    mass = float(scenario["mass_kg"])
    y0 = float(scenario["y0_m"])
    flight = model_input["times_s"][-1]
    states = []
    energy = 0.5 * mass * speed**2 + mass * g * y0
    for t in model_input["times_s"]:
        y = max(0.0, y0 + vy0 * t - 0.5 * g * t * t)
        vy = vy0 - g * t
        kinetic = 0.5 * mass * (vx0**2 + vy**2)
        potential = mass * g * y
        states.append(
            {
                "t_s": t,
                "x_m": float(scenario["x0_m"]) + vx0 * t,
                "y_m": y,
                "vx_m_s": vx0,
                "vy_m_s": vy,
                "ax_m_s2": 0.0,
                "ay_m_s2": -g,
                "kinetic_j": kinetic,
                "potential_j": potential,
                "mechanical_j": energy,
            }
        )
    apex = max(0.0, vy0 / g)
    return {
        "states": states,
        "events": {
            "flight_time_s": flight,
            "range_m": vx0 * flight,
            "apex_time_s": apex,
            "max_height_m": y0 + vy0**2 / (2 * g),
            "optimal_equal_height_angle_deg": 45.0,
        },
    }


def circular_output(
    scenario: dict[str, float | str],
    angles_rad: list[float] | None = None,
) -> dict[str, object]:
    model_input = circular_input(scenario)
    if angles_rad is not None:
        model_input["angles_rad"] = angles_rad
    mass = float(scenario["mass_kg"])
    radius = float(scenario["radius_m"])
    g = float(scenario["g_m_s2"])
    bottom_speed = float(scenario["speed_m_s"])
    states = []
    for theta in model_input["angles_rad"]:
        y = radius * (1 - math.cos(theta))
        speed = math.sqrt(max(0.0, bottom_speed**2 - 2 * g * y))
        accel = speed**2 / radius
        kinetic = 0.5 * mass * speed**2
        potential = mass * g * y
        states.append(
            {
                "angle_rad": theta,
                "x_m": radius * math.sin(theta),
                "y_m": y,
                "speed_m_s": speed,
                "ax_m_s2": -accel * math.sin(theta),
                "ay_m_s2": accel * math.cos(theta),
                "radial_force_n": mass * accel,
                "tension_n": mass * accel + mass * g * math.cos(theta),
                "kinetic_j": kinetic,
                "potential_j": potential,
                "mechanical_j": kinetic + potential,
            }
        )
    period = 2 * math.pi * radius / bottom_speed
    if scenario["mode"] == "vertical_string" and bottom_speed**2 >= 5 * g * radius:
        intervals = 20000
        step = 2 * math.pi / intervals
        period = 0.0
        for index in range(intervals):
            theta = (index + 0.5) * step
            height = radius * (1 - math.cos(theta))
            period += radius * step / math.sqrt(bottom_speed**2 - 2 * g * height)
    elif scenario["mode"] == "vertical_string":
        period = 0.0
    events = {
        "period_s": period,
        "centripetal_acceleration_m_s2": bottom_speed**2 / radius,
    }
    if scenario["mode"] == "vertical_string":
        events.update(
            {
                "critical_top_speed_m_s": math.sqrt(g * radius),
                "critical_bottom_speed_m_s": math.sqrt(5 * g * radius),
            }
        )
    return {"states": states, "events": events}


class GenericAssertionTests(unittest.TestCase):
    def test_dimension_assertion_has_positive_and_negative_cases(self) -> None:
        self.assertTrue(dimension_check("valid", VELOCITY, LENGTH / TIME).passed)
        self.assertFalse(dimension_check("invalid", VELOCITY, ACCELERATION).passed)


class ProjectileAssertionTests(unittest.TestCase):
    def test_all_projectile_assertions_accept_independent_correct_states(self) -> None:
        report = validate_projectile(PROJECTILE, projectile_output(PROJECTILE))
        self.assertTrue(report.passed, report.as_dict())

    def test_kinematics_direction_energy_and_critical_errors_each_fail(self) -> None:
        mutations = [
            ("x_kinematics", lambda output: output["states"][3].__setitem__("x_m", 999.0)),
            ("velocity_direction", lambda output: output["states"][2].__setitem__("vy_m_s", 99.0)),
            ("energy", lambda output: output["states"][4].__setitem__("mechanical_j", 1.0)),
            ("critical", lambda output: output["events"].__setitem__("apex_time_s", 99.0)),
            ("range_optimum", lambda output: output["events"].__setitem__("optimal_equal_height_angle_deg", 35.0)),
        ]
        for label, mutate in mutations:
            with self.subTest(label=label):
                output = projectile_output(PROJECTILE)
                mutate(output)
                self.assertFalse(validate_projectile(PROJECTILE, output).passed)

    def test_model_cannot_ignore_requested_time_axis(self) -> None:
        requested = projectile_input(PROJECTILE, sample_count=7)
        report = validate_projectile(PROJECTILE, projectile_output(PROJECTILE), requested["times_s"])
        self.assertIn("sample_count_matches_input", report.as_dict()["failed"])


class CircularAssertionTests(unittest.TestCase):
    def test_all_vertical_circle_assertions_accept_correct_states(self) -> None:
        report = validate_circular(VERTICAL, circular_output(VERTICAL))
        self.assertTrue(report.passed, report.as_dict())

    def test_geometry_direction_force_energy_and_critical_errors_each_fail(self) -> None:
        mutations = [
            ("geometry", lambda output: output["states"][2].__setitem__("x_m", 8.0)),
            ("inward_direction", lambda output: output["states"][3].__setitem__("ax_m_s2", 8.0)),
            ("radial_force", lambda output: output["states"][1].__setitem__("radial_force_n", 0.0)),
            ("energy", lambda output: output["states"][4].__setitem__("mechanical_j", 0.0)),
            ("critical", lambda output: output["events"].__setitem__("critical_top_speed_m_s", 0.0)),
        ]
        for label, mutate in mutations:
            with self.subTest(label=label):
                output = circular_output(VERTICAL)
                mutate(output)
                self.assertFalse(validate_circular(VERTICAL, output).passed)

    def test_subcritical_vertical_circle_is_rejected(self) -> None:
        scenario = {**VERTICAL, "speed_m_s": 8.0}
        self.assertFalse(validate_circular(scenario, circular_output(scenario)).passed)

    def test_vertical_probe_variations_remain_valid_complete_circles(self) -> None:
        from research.generation.harness.domains.circular import circular_probe_inputs

        for model_input in circular_probe_inputs(VERTICAL):
            output = circular_output(model_input["scenario"], model_input["angles_rad"])
            report = validate_circular(model_input["scenario"], output, model_input["angles_rad"])
            self.assertTrue(report.passed, report.as_dict())

    def test_constant_speed_period_formula_is_rejected_for_vertical_circle(self) -> None:
        output = circular_output(VERTICAL)
        output["events"]["period_s"] = 2 * math.pi * float(VERTICAL["radius_m"]) / float(VERTICAL["speed_m_s"])
        report = validate_circular(VERTICAL, output)
        self.assertIn("period_relation", report.as_dict()["failed"])

    def test_model_cannot_ignore_requested_angle_axis(self) -> None:
        from research.generation.harness.domains.circular import circular_input

        requested = circular_input(VERTICAL, sample_count=7)
        report = validate_circular(VERTICAL, circular_output(VERTICAL), requested["angles_rad"])
        self.assertIn("sample_count_matches_input", report.as_dict()["failed"])
