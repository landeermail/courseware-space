"""Independent reference assertions for uniform, orbital, and vertical circular motion."""

from __future__ import annotations

import math
from typing import Any

from harness.assertions import (
    ACCELERATION,
    ENERGY,
    FORCE,
    LENGTH,
    MASS,
    TIME,
    VELOCITY,
    Check,
    close_check,
    dimension_check,
    finite_check,
    report,
    true_check,
)


COMMON = {"mode", "mass_kg", "radius_m", "g_m_s2", "speed_m_s", "central_mass_kg", "G_n_m2_kg2"}


def normalize_circular(scenario: dict[str, Any]) -> dict[str, float | str | None]:
    if not isinstance(scenario, dict) or set(scenario) != COMMON:
        raise ValueError("圆周场景字段不符合白名单")
    if scenario["mode"] not in {"uniform", "orbit", "vertical_string"}:
        raise ValueError("圆周 mode 无效")
    output: dict[str, float | str | None] = {"mode": scenario["mode"]}
    limits = {
        "mass_kg": (0.001, 1e8),
        "radius_m": (0.01, 1e12),
        "g_m_s2": (0.1, 30.0),
        "speed_m_s": (0.0, 1e7),
        "central_mass_kg": (0.0, 1e35),
        "G_n_m2_kg2": (1e-12, 1e-9),
    }
    for key, (lower, upper) in limits.items():
        value = scenario[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            raise ValueError(f"{key} 必须是有限数值")
        value = float(value)
        if not lower <= value <= upper:
            raise ValueError(f"{key} 超出验证范围")
        output[key] = value
    mode = output["mode"]
    if mode == "orbit":
        if float(output["central_mass_kg"]) <= 0 or float(output["speed_m_s"]) != 0.0:
            raise ValueError("卫星模式由中心天体质量与半径独立确定速度")
    elif float(output["speed_m_s"]) <= 0 or float(output["central_mass_kg"]) != 0.0:
        raise ValueError("非卫星模式必须给定速度且 central_mass_kg=0")
    return output


def _speed(s: dict[str, Any]) -> float:
    if s["mode"] == "orbit":
        return math.sqrt(float(s["G_n_m2_kg2"]) * float(s["central_mass_kg"]) / float(s["radius_m"]))
    return float(s["speed_m_s"])


def _vertical_period(bottom_speed: float, g: float, radius: float, intervals: int = 4096) -> float:
    """Numerically integrate dt=r*dtheta/v(theta) for a complete vertical circle."""

    if intervals < 2 or intervals % 2:
        raise ValueError("Simpson intervals must be a positive even number")

    def inverse_angular_speed(theta: float) -> float:
        height = radius * (1.0 - math.cos(theta))
        speed_sq = bottom_speed**2 - 2.0 * g * height
        if speed_sq <= 0:
            raise ValueError("竖直圆周速度不足以完成积分")
        return radius / math.sqrt(speed_sq)

    step = 2.0 * math.pi / intervals
    total = inverse_angular_speed(0.0) + inverse_angular_speed(2.0 * math.pi)
    for index in range(1, intervals):
        total += (4.0 if index % 2 else 2.0) * inverse_angular_speed(index * step)
    return total * step / 3.0


def circular_input(scenario: dict[str, Any], sample_count: int = 9) -> dict[str, Any]:
    s = normalize_circular(scenario)
    if s["mode"] == "vertical_string":
        angles = [2.0 * math.pi * index / (sample_count - 1) for index in range(sample_count)]
    else:
        angles = [2.0 * math.pi * index / sample_count for index in range(sample_count)]
    return {"scenario": s, "angles_rad": angles}


def circular_probe_inputs(scenario: dict[str, Any]) -> list[dict[str, Any]]:
    """Probe unseen radii/speeds/masses so formulas must remain dynamic."""

    s = normalize_circular(scenario)
    variations = [dict(s)]
    radius_low = max(0.01, float(s["radius_m"]) * 0.8)
    radius_high = min(1e12, float(s["radius_m"]) * 1.2)
    if s["mode"] == "vertical_string":
        original_radius = float(s["radius_m"])
        original_speed = float(s["speed_m_s"])
        variations.append({**s, "radius_m": radius_low, "speed_m_s": original_speed * math.sqrt(radius_low / original_radius)})
        variations.append({**s, "radius_m": radius_high, "speed_m_s": original_speed * math.sqrt(radius_high / original_radius)})
    else:
        variations.append({**s, "radius_m": radius_low})
        variations.append({**s, "radius_m": radius_high})
    variations.append({**s, "mass_kg": max(0.001, float(s["mass_kg"]) * 1.3)})
    if s["mode"] == "orbit":
        variations.append({**s, "central_mass_kg": float(s["central_mass_kg"]) * 0.75})
        variations.append({**s, "central_mass_kg": float(s["central_mass_kg"]) * 1.25})
    else:
        low = float(s["speed_m_s"]) * 0.9
        if s["mode"] == "vertical_string":
            low = max(low, math.sqrt(5.0 * float(s["g_m_s2"]) * float(s["radius_m"])) * 1.01)
        variations.append({**s, "speed_m_s": low})
        variations.append({**s, "speed_m_s": float(s["speed_m_s"]) * 1.1})
    sample_counts = (9, 8, 11, 10, 12, 7)
    return [circular_input(variation, sample_counts[index]) for index, variation in enumerate(variations)]


def validate_circular(
    scenario: dict[str, Any],
    output: dict[str, Any],
    expected_angles_rad: list[float] | None = None,
) -> Any:
    s = normalize_circular(scenario)
    checks: list[Check] = [
        dimension_check("dimension_centripetal_acceleration", ACCELERATION, (VELOCITY**2) / LENGTH),
        dimension_check("dimension_centripetal_force", FORCE, MASS * (VELOCITY**2) / LENGTH),
        dimension_check("dimension_period", TIME, LENGTH / VELOCITY),
        dimension_check("dimension_energy", ENERGY, MASS * (VELOCITY**2)),
    ]
    if not isinstance(output, dict) or set(output) != {"states", "events"}:
        return report("circular", checks + [true_check("output_contract", False, "输出必须只有 states/events")])
    states = output["states"]
    events = output["events"]
    if not isinstance(states, list) or len(states) < 5 or not isinstance(events, dict):
        return report("circular", checks + [true_check("state_contract", False, "states/events 结构无效")])
    required_state = {"angle_rad", "x_m", "y_m", "speed_m_s", "ax_m_s2", "ay_m_s2", "radial_force_n", "tension_n", "kinetic_j", "potential_j", "mechanical_j"}
    state_contract = all(isinstance(state, dict) and set(state) == required_state for state in states)
    checks.append(true_check("state_fields_exact", state_contract, "每个状态必须使用精确字段白名单"))
    if not state_contract:
        return report("circular", checks)
    checks.append(finite_check("states_are_finite", [state[key] for state in states for key in required_state]))
    if expected_angles_rad is not None:
        checks.append(
            true_check(
                "sample_count_matches_input",
                len(states) == len(expected_angles_rad),
                "states 数量必须与 angles_rad 一致",
            )
        )
        for index, (state, expected_angle) in enumerate(zip(states, expected_angles_rad)):
            checks.append(close_check(f"state_{index}_angle_matches_input", state["angle_rad"], expected_angle))

    mode = str(s["mode"])
    mass = float(s["mass_kg"])
    radius = float(s["radius_m"])
    g = float(s["g_m_s2"])
    base_speed = _speed(s)
    energy0 = 0.5 * mass * base_speed**2
    for index, state in enumerate(states):
        theta = float(state["angle_rad"])
        x = radius * math.cos(theta) if mode != "vertical_string" else radius * math.sin(theta)
        y = radius * math.sin(theta) if mode != "vertical_string" else radius * (1.0 - math.cos(theta))
        if mode == "vertical_string":
            speed_sq = base_speed**2 - 2.0 * g * y
            expected_speed = math.sqrt(max(0.0, speed_sq))
            tension = mass * expected_speed**2 / radius + mass * g * math.cos(theta)
            potential = mass * g * y
        else:
            expected_speed = base_speed
            tension = 0.0
            potential = -float(s["G_n_m2_kg2"]) * float(s["central_mass_kg"]) * mass / radius if mode == "orbit" else 0.0
            energy0 = 0.5 * mass * expected_speed**2 + potential
        accel = expected_speed**2 / radius
        ax = -accel * math.cos(theta) if mode != "vertical_string" else -accel * math.sin(theta)
        ay = -accel * math.sin(theta) if mode != "vertical_string" else accel * math.cos(theta)
        radial_force = mass * accel
        kinetic = 0.5 * mass * expected_speed**2
        checks.extend(
            [
                close_check(f"state_{index}_x_geometry", state["x_m"], x),
                close_check(f"state_{index}_y_geometry", state["y_m"], y),
                close_check(f"state_{index}_speed", state["speed_m_s"], expected_speed),
                close_check(f"state_{index}_ax_inward", state["ax_m_s2"], ax),
                close_check(f"state_{index}_ay_inward", state["ay_m_s2"], ay),
                close_check(f"state_{index}_radial_force", state["radial_force_n"], radial_force),
                close_check(f"state_{index}_tension", state["tension_n"], tension),
                close_check(f"state_{index}_kinetic", state["kinetic_j"], kinetic),
                close_check(f"state_{index}_potential", state["potential_j"], potential),
                close_check(f"state_{index}_energy_sum", state["mechanical_j"], kinetic + potential),
                close_check(f"state_{index}_energy_conserved", state["mechanical_j"], energy0),
            ]
        )
    event_fields = {"period_s", "centripetal_acceleration_m_s2"}
    if mode == "vertical_string":
        event_fields |= {"critical_top_speed_m_s", "critical_bottom_speed_m_s"}
    checks.append(true_check("event_fields_exact", set(events) == event_fields, "事件字段必须精确匹配"))
    if set(events) == event_fields:
        if mode == "vertical_string" and base_speed**2 < 5.0 * g * radius - 1e-9:
            checks.append(true_check("period_defined_for_complete_circle", False, "亚临界速度不能定义完整竖直圆周周期"))
        else:
            period = _vertical_period(base_speed, g, radius) if mode == "vertical_string" else 2.0 * math.pi * radius / base_speed
            checks.append(
                close_check(
                    "period_relation",
                    events["period_s"],
                    period,
                    rel_tol=2e-4 if mode == "vertical_string" else 1e-7,
                )
            )
        checks.append(close_check("centripetal_acceleration_relation", events["centripetal_acceleration_m_s2"], base_speed**2 / radius))
        if mode == "vertical_string":
            checks.extend(
                [
                    close_check("vertical_top_critical", events["critical_top_speed_m_s"], math.sqrt(g * radius)),
                    close_check("vertical_bottom_critical", events["critical_bottom_speed_m_s"], math.sqrt(5.0 * g * radius)),
                ]
            )
    if mode == "vertical_string":
        top_speed_sq = base_speed**2 - 4.0 * g * radius
        checks.append(true_check("string_tension_nonnegative", top_speed_sq >= g * radius - 1e-9, "完整竖直圆周要求最高点张力非负"))
    if mode == "orbit":
        gravity_force = float(s["G_n_m2_kg2"]) * float(s["central_mass_kg"]) * mass / radius**2
        checks.append(close_check("gravity_supplies_centripetal_force", gravity_force, mass * base_speed**2 / radius))
    return report("circular", checks)
