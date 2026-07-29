"""Independent reference assertions for horizontal and oblique projectile motion."""

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


REQUIRED = {"mode", "g_m_s2", "mass_kg", "x0_m", "y0_m", "speed_m_s", "angle_deg"}


def normalize_projectile(scenario: dict[str, Any]) -> dict[str, float | str]:
    if not isinstance(scenario, dict) or set(scenario) != REQUIRED:
        raise ValueError("抛体场景字段不符合白名单")
    if scenario["mode"] not in {"horizontal", "oblique"}:
        raise ValueError("抛体 mode 只允许 horizontal 或 oblique")
    normalized: dict[str, float | str] = {"mode": scenario["mode"]}
    limits = {
        "g_m_s2": (1.0, 20.0),
        "mass_kg": (0.01, 100.0),
        "x0_m": (-1000.0, 1000.0),
        "y0_m": (0.0, 1000.0),
        "speed_m_s": (0.1, 300.0),
        "angle_deg": (0.0, 89.0),
    }
    for key, (lower, upper) in limits.items():
        value = scenario[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            raise ValueError(f"{key} 必须是有限数值")
        value = float(value)
        if not lower <= value <= upper:
            raise ValueError(f"{key} 超出验证范围")
        normalized[key] = value
    if normalized["mode"] == "horizontal" and normalized["angle_deg"] != 0.0:
        raise ValueError("平抛初速度必须水平")
    if normalized["mode"] == "oblique" and not 0.0 < float(normalized["angle_deg"]) < 89.0:
        raise ValueError("斜抛角必须在 0°～89°")
    if float(normalized["y0_m"]) == 0.0 and normalized["mode"] == "horizontal":
        raise ValueError("平抛必须从地面以上开始")
    return normalized


def _reference(scenario: dict[str, Any]) -> dict[str, float]:
    s = normalize_projectile(scenario)
    angle = math.radians(float(s["angle_deg"]))
    vx0 = float(s["speed_m_s"]) * math.cos(angle)
    vy0 = float(s["speed_m_s"]) * math.sin(angle)
    g = float(s["g_m_s2"])
    y0 = float(s["y0_m"])
    flight = (vy0 + math.sqrt(vy0 * vy0 + 2.0 * g * y0)) / g
    apex = vy0 / g if vy0 > 0 else 0.0
    return {
        "vx0": vx0,
        "vy0": vy0,
        "flight_time_s": flight,
        "apex_time_s": apex,
        "range_m": vx0 * flight,
        "max_height_m": y0 + vy0 * vy0 / (2.0 * g),
    }


def projectile_input(scenario: dict[str, Any], sample_count: int = 9) -> dict[str, Any]:
    s = normalize_projectile(scenario)
    ref = _reference(s)
    times = [ref["flight_time_s"] * index / (sample_count - 1) for index in range(sample_count)]
    return {"scenario": s, "times_s": times}


def projectile_probe_inputs(scenario: dict[str, Any]) -> list[dict[str, Any]]:
    """Metamorphic probes prevent a generated model from hard-coding one answer."""

    s = normalize_projectile(scenario)
    variations = [dict(s)]
    variations.append({**s, "speed_m_s": max(0.1, float(s["speed_m_s"]) * 0.8)})
    variations.append({**s, "speed_m_s": min(300.0, float(s["speed_m_s"]) * 1.2)})
    variations.append({**s, "g_m_s2": min(20.0, max(1.0, float(s["g_m_s2"]) * 0.9))})
    if s["mode"] == "oblique":
        variations.append({**s, "angle_deg": max(5.0, float(s["angle_deg"]) - 10.0)})
        variations.append({**s, "angle_deg": min(80.0, float(s["angle_deg"]) + 10.0)})
    else:
        variations.append({**s, "y0_m": min(1000.0, max(0.1, float(s["y0_m"]) * 1.25))})
    sample_counts = (9, 7, 11, 8, 10, 12)
    return [projectile_input(variation, sample_counts[index]) for index, variation in enumerate(variations)]


def validate_projectile(
    scenario: dict[str, Any],
    output: dict[str, Any],
    expected_times_s: list[float] | None = None,
) -> Any:
    s = normalize_projectile(scenario)
    reference = _reference(s)
    checks: list[Check] = [
        dimension_check("dimension_x_equals_vt", LENGTH, VELOCITY * TIME),
        dimension_check("dimension_v_equals_at", VELOCITY, ACCELERATION * TIME),
        dimension_check("dimension_energy_is_force_length", ENERGY, FORCE * LENGTH),
        dimension_check("dimension_kinetic_is_mass_v2", ENERGY, MASS * (VELOCITY**2)),
    ]
    if not isinstance(output, dict) or set(output) != {"states", "events"}:
        return report("projectile", checks + [true_check("output_contract", False, "输出必须只有 states/events")])
    states = output["states"]
    events = output["events"]
    if not isinstance(states, list) or len(states) < 5 or not isinstance(events, dict):
        return report("projectile", checks + [true_check("state_contract", False, "states/events 结构无效")])

    required_state = {"t_s", "x_m", "y_m", "vx_m_s", "vy_m_s", "ax_m_s2", "ay_m_s2", "kinetic_j", "potential_j", "mechanical_j"}
    state_contract = all(isinstance(state, dict) and set(state) == required_state for state in states)
    checks.append(true_check("state_fields_exact", state_contract, "每个状态必须使用精确字段白名单"))
    if not state_contract:
        return report("projectile", checks)

    numeric_values = [state[key] for state in states for key in required_state]
    checks.append(finite_check("states_are_finite", numeric_values))
    if expected_times_s is not None:
        checks.append(
            true_check(
                "sample_count_matches_input",
                len(states) == len(expected_times_s),
                "states 数量必须与 times_s 一致",
            )
        )
        for index, (state, expected_time) in enumerate(zip(states, expected_times_s)):
            checks.append(close_check(f"state_{index}_time_matches_input", state["t_s"], expected_time))
    g = float(s["g_m_s2"])
    mass = float(s["mass_kg"])
    x0 = float(s["x0_m"])
    y0 = float(s["y0_m"])
    energy0 = 0.5 * mass * float(s["speed_m_s"]) ** 2 + mass * g * y0
    for index, state in enumerate(states):
        t = float(state["t_s"])
        expected_x = x0 + reference["vx0"] * t
        expected_y = y0 + reference["vy0"] * t - 0.5 * g * t * t
        expected_vy = reference["vy0"] - g * t
        kinetic = 0.5 * mass * (reference["vx0"] ** 2 + expected_vy**2)
        potential = mass * g * max(0.0, expected_y)
        checks.extend(
            [
                close_check(f"state_{index}_x_kinematics", state["x_m"], expected_x),
                close_check(f"state_{index}_y_kinematics", state["y_m"], max(0.0, expected_y)),
                close_check(f"state_{index}_vx_constant", state["vx_m_s"], reference["vx0"]),
                close_check(f"state_{index}_vy_linear", state["vy_m_s"], expected_vy),
                close_check(f"state_{index}_ax_zero", state["ax_m_s2"], 0.0),
                close_check(f"state_{index}_ay_gravity", state["ay_m_s2"], -g),
                close_check(f"state_{index}_kinetic", state["kinetic_j"], kinetic),
                close_check(f"state_{index}_potential", state["potential_j"], potential),
                close_check(f"state_{index}_energy_conserved", state["mechanical_j"], energy0),
                close_check(f"state_{index}_energy_sum", state["mechanical_j"], float(state["kinetic_j"]) + float(state["potential_j"])),
            ]
        )
    event_fields = {"flight_time_s", "range_m", "apex_time_s", "max_height_m", "optimal_equal_height_angle_deg"}
    checks.append(true_check("event_fields_exact", set(events) == event_fields, "事件字段必须精确匹配"))
    if set(events) == event_fields:
        checks.extend(
            [
                close_check("flight_time_boundary", events["flight_time_s"], reference["flight_time_s"]),
                close_check("range_boundary", events["range_m"], reference["range_m"]),
                close_check("apex_vy_zero_time", events["apex_time_s"], reference["apex_time_s"]),
                close_check("max_height_boundary", events["max_height_m"], reference["max_height_m"]),
                close_check("equal_height_range_optimum", events["optimal_equal_height_angle_deg"], 45.0),
            ]
        )
    return report("projectile", checks)
