#!/usr/bin/env python3
"""Independent standard-library reference for the two charged balls on a ring."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


RADIUS_M = 1.0
MASS_KG = 1.0
GRAVITY = 9.8
BASE_GAMMA = 1.0 / math.sqrt(3.0)  # kq0^2 / (mgR^2)
PUSH_ANGLES_DEG = (30, 24, 18, 12, 6, 0)
CHARGE_SCALES = (0.8, 1.0, 1.2)


def _equilibrium_residual(beta: float, alpha: float, gamma: float) -> float:
    half_sum = 0.5 * (alpha + beta)
    electrostatic_tangent = (
        gamma * math.cos(half_sum) / (4.0 * math.sin(half_sum) ** 2)
    )
    return electrostatic_tangent - math.sin(beta)


def solve_beta(alpha: float, charge_scale: float = 1.0) -> float:
    """Solve b's tangential equilibrium for a fixed position of a."""

    gamma = BASE_GAMMA * charge_scale**2
    lower = 1e-8
    upper = 0.5 * math.pi - 1e-8
    low_value = _equilibrium_residual(lower, alpha, gamma)
    high_value = _equilibrium_residual(upper, alpha, gamma)
    if low_value <= 0 or high_value >= 0:
        raise ValueError("equilibrium root is not bracketed")
    for _ in range(90):
        middle = 0.5 * (lower + upper)
        value = _equilibrium_residual(middle, alpha, gamma)
        if value > 0:
            lower = middle
        else:
            upper = middle
    return 0.5 * (lower + upper)


def quasistatic_state(alpha_deg: float, charge_scale: float = 1.0) -> dict[str, float]:
    alpha = math.radians(alpha_deg)
    beta = solve_beta(alpha, charge_scale)
    half_sum = 0.5 * (alpha + beta)
    distance_ratio = 2.0 * math.sin(half_sum)
    gamma = BASE_GAMMA * charge_scale**2
    coulomb_over_mg = gamma / distance_ratio**2
    support_over_mg = math.cos(beta) + coulomb_over_mg * math.sin(half_sum)
    gravity_energy = -(math.cos(alpha) + math.cos(beta))
    electric_energy = gamma / distance_ratio
    external_tangent_over_mg = (
        math.sin(alpha) - coulomb_over_mg * math.cos(half_sum)
    )
    return {
        "alpha_deg": alpha_deg,
        "beta_deg": math.degrees(beta),
        "distance_over_r": distance_ratio,
        "coulomb_over_mg": coulomb_over_mg,
        "support_b_over_mg": support_over_mg,
        "external_tangent_over_mg": external_tangent_over_mg,
        "gravity_energy_over_mgr": gravity_energy,
        "electric_energy_over_mgr": electric_energy,
        "total_potential_over_mgr": gravity_energy + electric_energy,
        "tangent_balance_residual": _equilibrium_residual(beta, alpha, gamma),
    }


def quasistatic_path(charge_scale: float) -> list[dict[str, float]]:
    initial = quasistatic_state(30.0, charge_scale)
    initial_potential = initial["total_potential_over_mgr"]
    path: list[dict[str, float]] = []
    for alpha_half_degree in range(60, -1, -1):
        state = quasistatic_state(alpha_half_degree / 2.0, charge_scale)
        state["external_work_over_mgr"] = (
            state["total_potential_over_mgr"] - initial_potential
        )
        state["delta_gravity_energy_over_mgr"] = (
            state["gravity_energy_over_mgr"]
            - initial["gravity_energy_over_mgr"]
        )
        state["delta_electric_energy_over_mgr"] = (
            state["electric_energy_over_mgr"]
            - initial["electric_energy_over_mgr"]
        )
        path.append(state)
    return path


def _angular_accelerations(
    alpha: float, beta: float, charge_scale: float, *, coulomb_sign: float = 1.0
) -> tuple[float, float]:
    half_sum = 0.5 * (alpha + beta)
    gamma = BASE_GAMMA * charge_scale**2
    coulomb_term = (
        coulomb_sign
        * gamma
        * math.cos(half_sum)
        / (4.0 * math.sin(half_sum) ** 2)
    )
    factor = GRAVITY / RADIUS_M
    return (
        factor * (-math.sin(alpha) + coulomb_term),
        factor * (-math.sin(beta) + coulomb_term),
    )


def _dynamic_state(
    time_s: float,
    alpha: float,
    beta: float,
    alpha_velocity: float,
    beta_velocity: float,
    charge_scale: float,
) -> dict[str, float]:
    gamma = BASE_GAMMA * charge_scale**2
    half_sum = 0.5 * (alpha + beta)
    distance_ratio = 2.0 * math.sin(half_sum)
    kinetic = RADIUS_M * (
        alpha_velocity**2 + beta_velocity**2
    ) / (2.0 * GRAVITY)
    gravity_energy = -(math.cos(alpha) + math.cos(beta))
    electric_energy = gamma / distance_ratio
    return {
        "time_s": time_s,
        "alpha_deg": math.degrees(alpha),
        "beta_deg": math.degrees(beta),
        "alpha_velocity_rad_s": alpha_velocity,
        "beta_velocity_rad_s": beta_velocity,
        "distance_over_r": distance_ratio,
        "kinetic_over_mgr": kinetic,
        "gravity_energy_over_mgr": gravity_energy,
        "electric_energy_over_mgr": electric_energy,
        "total_energy_over_mgr": kinetic + gravity_energy + electric_energy,
    }


def simulate_release(
    alpha_deg: float,
    charge_scale: float,
    *,
    duration_s: float = 4.0,
    step_s: float = 0.001,
    sample_s: float = 0.02,
    coulomb_sign: float = 1.0,
) -> list[dict[str, float]]:
    """Velocity-Verlet reference motion after the external force is removed."""

    alpha = math.radians(alpha_deg)
    beta = solve_beta(alpha, charge_scale)
    alpha_velocity = 0.0
    beta_velocity = 0.0
    alpha_acc, beta_acc = _angular_accelerations(
        alpha, beta, charge_scale, coulomb_sign=coulomb_sign
    )
    steps = int(round(duration_s / step_s))
    sample_every = max(1, int(round(sample_s / step_s)))
    result = [
        _dynamic_state(
            0.0, alpha, beta, alpha_velocity, beta_velocity, charge_scale
        )
    ]
    for step in range(1, steps + 1):
        alpha += alpha_velocity * step_s + 0.5 * alpha_acc * step_s**2
        beta += beta_velocity * step_s + 0.5 * beta_acc * step_s**2
        new_alpha_acc, new_beta_acc = _angular_accelerations(
            alpha, beta, charge_scale, coulomb_sign=coulomb_sign
        )
        alpha_velocity += 0.5 * (alpha_acc + new_alpha_acc) * step_s
        beta_velocity += 0.5 * (beta_acc + new_beta_acc) * step_s
        alpha_acc, beta_acc = new_alpha_acc, new_beta_acc
        if step % sample_every == 0:
            result.append(
                _dynamic_state(
                    step * step_s,
                    alpha,
                    beta,
                    alpha_velocity,
                    beta_velocity,
                    charge_scale,
                )
            )
    return result


def _rounded(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 9)
    if isinstance(value, dict):
        return {key: _rounded(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_rounded(item) for item in value]
    return value


def build_reference_data() -> dict[str, Any]:
    quasi: dict[str, Any] = {}
    releases: dict[str, Any] = {}
    for scale in CHARGE_SCALES:
        scale_key = f"q{int(round(scale * 100)):03d}"
        quasi[scale_key] = quasistatic_path(scale)
        releases[scale_key] = {
            f"a{angle:02d}": simulate_release(angle, scale)
            for angle in PUSH_ANGLES_DEG
        }
    return _rounded(
        {
            "meta": {
                "model": "two-identical-charged-balls-on-vertical-ring",
                "units": "R=m=1, g=9.8; forces in mg; energies in mgR",
                "base_gamma": BASE_GAMMA,
                "charge_scales": list(CHARGE_SCALES),
                "push_angles_deg": list(PUSH_ANGLES_DEG),
                "physical_duration_s": 4.0,
                "sample_interval_s": 0.02,
            },
            "quasistatic": quasi,
            "release": releases,
        }
    )


def self_check(*, coulomb_sign: float = 1.0) -> list[str]:
    errors: list[str] = []
    initial = quasistatic_state(30.0)
    final = quasistatic_state(0.0)
    if abs(initial["distance_over_r"] - 1.0) > 1e-9:
        errors.append("initial chord is not R")
    if not final["support_b_over_mg"] < initial["support_b_over_mg"]:
        errors.append("b support force did not decrease")
    delta_g = final["gravity_energy_over_mgr"] - initial["gravity_energy_over_mgr"]
    delta_e = final["electric_energy_over_mgr"] - initial["electric_energy_over_mgr"]
    work = final["total_potential_over_mgr"] - initial["total_potential_over_mgr"]
    if abs(work - delta_g - delta_e) > 1e-11 or work <= 0 or delta_e <= 0:
        errors.append("quasistatic energy ledger is inconsistent")
    motion = simulate_release(0.0, 1.0, coulomb_sign=coulomb_sign)
    initial_energy = motion[0]["total_energy_over_mgr"]
    drift = max(abs(item["total_energy_over_mgr"] - initial_energy) for item in motion)
    if drift > 2e-5:
        errors.append(f"post-release energy drift too large: {drift:.6g}")
    # At c, gravity has no tangential component on a; repulsion must accelerate it away from b.
    if motion[1]["alpha_deg"] <= motion[0]["alpha_deg"]:
        errors.append("Coulomb direction is reversed after release")
    return errors


def write_red_green_evidence(path: Path) -> bool:
    red_errors = self_check(coulomb_sign=-1.0)
    green_errors = self_check(coulomb_sign=1.0)
    payload = {
        "fault": "reverse the Coulomb tangential direction after release",
        "red": {"passed": not red_errors, "errors": red_errors},
        "green": {"passed": not green_errors, "errors": green_errors},
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return bool(red_errors) and not green_errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--fault", choices=("wrong-coulomb-direction",))
    parser.add_argument("--red-green-evidence", type=Path)
    args = parser.parse_args()

    if args.output:
        args.output.write_text(
            json.dumps(build_reference_data(), ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        print(f"wrote {args.output}")
    if args.red_green_evidence:
        if not write_red_green_evidence(args.red_green_evidence):
            print("red→green evidence failed")
            return 1
        print(f"red→green evidence passed: {args.red_green_evidence}")
    if args.self_check:
        sign = -1.0 if args.fault else 1.0
        errors = self_check(coulomb_sign=sign)
        if errors:
            for error in errors:
                print(f"FAIL: {error}")
            return 1
        print("physics reference self-check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
