"""Locked physics model for a conducting rod sliding on parallel rails.

Coordinate convention:
- +x points right along the rails.
- +y points from endpoint d to endpoint c along the rod.
- +z points out of the page.

The AI-facing configuration contains only scalar parameters and enum values.
All derived electromagnetic quantities and directions are computed here.
"""

from __future__ import annotations

import math
from typing import Any


SCHEMA_VERSION = 1
MODEL_VERSION = "conducting-rod-uniform-field-v1"

REQUIRED_KEYS = {
    "schema_version",
    "title",
    "source_text",
    "magnetic_field_t",
    "rod_length_m",
    "rod_speed_m_s",
    "resistance_ohm",
    "field_direction",
    "motion_direction",
    "duration_s",
}

LIMITS = {
    "magnetic_field_t": (0.01, 5.0),
    "rod_length_m": (0.10, 5.0),
    "rod_speed_m_s": (0.01, 50.0),
    "resistance_ohm": (0.001, 100.0),
    "duration_s": (0.5, 10.0),
}


class ModelValidationError(ValueError):
    """Raised when an AI-provided configuration is outside the template scope."""


def _number(raw: dict[str, Any], key: str) -> float:
    value = raw[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ModelValidationError(f"{key} 必须是有限数值")
    value = float(value)
    if not math.isfinite(value):
        raise ModelValidationError(f"{key} 必须是有限数值")
    lower, upper = LIMITS[key]
    if not lower <= value <= upper:
        raise ModelValidationError(f"{key}={value:g} 超出模板范围 [{lower:g}, {upper:g}]")
    return value


def _text(raw: dict[str, Any], key: str, minimum: int, maximum: int) -> str:
    value = raw[key]
    if not isinstance(value, str):
        raise ModelValidationError(f"{key} 必须是字符串")
    value = " ".join(value.split())
    if not minimum <= len(value) <= maximum:
        raise ModelValidationError(f"{key} 长度必须在 {minimum}～{maximum} 个字符之间")
    return value


def normalize_config(raw: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize the only structure an AI may provide."""

    if not isinstance(raw, dict):
        raise ModelValidationError("配置必须是 JSON 对象")
    missing = REQUIRED_KEYS - raw.keys()
    extra = raw.keys() - REQUIRED_KEYS
    if missing:
        raise ModelValidationError(f"缺少字段：{', '.join(sorted(missing))}")
    if extra:
        raise ModelValidationError(f"不允许的字段：{', '.join(sorted(extra))}")
    if raw["schema_version"] != SCHEMA_VERSION:
        raise ModelValidationError(f"schema_version 必须为 {SCHEMA_VERSION}")
    if raw["field_direction"] not in {"into_page", "out_of_page"}:
        raise ModelValidationError("field_direction 只允许 into_page 或 out_of_page")
    if raw["motion_direction"] not in {"left", "right"}:
        raise ModelValidationError("motion_direction 只允许 left 或 right")

    return {
        "schema_version": SCHEMA_VERSION,
        "title": _text(raw, "title", 4, 80),
        "source_text": _text(raw, "source_text", 8, 500),
        "magnetic_field_t": _number(raw, "magnetic_field_t"),
        "rod_length_m": _number(raw, "rod_length_m"),
        "rod_speed_m_s": _number(raw, "rod_speed_m_s"),
        "resistance_ohm": _number(raw, "resistance_ohm"),
        "field_direction": raw["field_direction"],
        "motion_direction": raw["motion_direction"],
        "duration_s": _number(raw, "duration_s"),
    }


def derive_physics(config: dict[str, Any], speed_multiplier: float = 1.0) -> dict[str, Any]:
    """Derive every displayed quantity from validated parameters."""

    config = normalize_config(config)
    if isinstance(speed_multiplier, bool) or not isinstance(speed_multiplier, (int, float)):
        raise ModelValidationError("speed_multiplier 必须是数值")
    speed_multiplier = float(speed_multiplier)
    if not math.isfinite(speed_multiplier) or not 0.25 <= speed_multiplier <= 2.0:
        raise ModelValidationError("speed_multiplier 必须在 0.25～2.0 之间")

    motion_sign = 1 if config["motion_direction"] == "right" else -1
    field_sign = 1 if config["field_direction"] == "out_of_page" else -1
    current_sign = -motion_sign * field_sign
    induced_field_sign = current_sign
    force_sign = current_sign * field_sign

    field = config["magnetic_field_t"]
    length = config["rod_length_m"]
    speed = config["rod_speed_m_s"] * speed_multiplier
    resistance = config["resistance_ohm"]
    emf = field * length * speed
    current = emf / resistance
    magnetic_force = field * current * length
    joule_power = current * current * resistance
    mechanical_power = magnetic_force * speed

    return {
        "model_version": MODEL_VERSION,
        "speed_multiplier": speed_multiplier,
        "speed_m_s": speed,
        "emf_v": emf,
        "current_a": current,
        "magnetic_force_n": magnetic_force,
        "joule_power_w": joule_power,
        "mechanical_power_w": mechanical_power,
        "motion_sign": motion_sign,
        "field_sign": field_sign,
        "current_sign": current_sign,
        "force_sign": force_sign,
        "induced_field_sign": induced_field_sign,
        "motion_label": "向右" if motion_sign > 0 else "向左",
        "field_label": "垂直纸面向外" if field_sign > 0 else "垂直纸面向里",
        "field_symbol": "•" if field_sign > 0 else "×",
        "rod_current_label": "d → c（沿棒向上）" if current_sign > 0 else "c → d（沿棒向下）",
        "circuit_label": "逆时针" if current_sign > 0 else "顺时针",
        "high_potential_endpoint": "c" if current_sign > 0 else "d",
        "force_label": "向右" if force_sign > 0 else "向左",
        "induced_field_label": "垂直纸面向外" if induced_field_sign > 0 else "垂直纸面向里",
    }


def physics_assertions(config: dict[str, Any], model: dict[str, Any] | None = None) -> dict[str, bool]:
    """Return named physical invariants suitable for machine validation."""

    config = normalize_config(config)
    model = model or derive_physics(config)
    field = config["magnetic_field_t"]
    length = config["rod_length_m"]
    speed = model["speed_m_s"]
    resistance = config["resistance_ohm"]
    flux_change_sign = model["field_sign"] * model["motion_sign"]

    return {
        "emf_is_Blv": math.isclose(model["emf_v"], field * length * speed, rel_tol=1e-12),
        "current_is_emf_over_R": math.isclose(model["current_a"], model["emf_v"] / resistance, rel_tol=1e-12),
        "force_is_BIl": math.isclose(model["magnetic_force_n"], field * model["current_a"] * length, rel_tol=1e-12),
        "magnetic_force_opposes_motion": model["force_sign"] == -model["motion_sign"],
        "lenz_field_opposes_flux_change": model["induced_field_sign"] == -flux_change_sign,
        "joule_power_is_I2R": math.isclose(model["joule_power_w"], model["current_a"] ** 2 * resistance, rel_tol=1e-12),
        "mechanical_power_equals_joule_power": math.isclose(model["mechanical_power_w"], model["joule_power_w"], rel_tol=1e-12),
        "displayed_values_are_nonnegative": all(
            model[key] >= 0
            for key in ("speed_m_s", "emf_v", "current_a", "magnetic_force_n", "joule_power_w")
        ),
    }


def assert_physics(config: dict[str, Any], model: dict[str, Any] | None = None) -> dict[str, Any]:
    """Reject a configuration or derived result when any invariant fails."""

    model = model or derive_physics(config)
    failed = [name for name, passed in physics_assertions(config, model).items() if not passed]
    if failed:
        raise ModelValidationError(f"物理断言失败：{', '.join(failed)}")
    return model
