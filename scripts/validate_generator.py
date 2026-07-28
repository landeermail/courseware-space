#!/usr/bin/env python3
"""Validate generator templates without changing the existing site validator."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_ROOT = ROOT / "templates" / "conducting-rod"
sys.path.insert(0, str(TEMPLATE_ROOT))

from physics import (  # noqa: E402
    ModelValidationError,
    assert_physics,
    derive_physics,
    normalize_config,
    physics_assertions,
)


def fail(message: str) -> None:
    raise AssertionError(message)


def validate_examples() -> list[tuple[str, dict[str, object]]]:
    cases = sorted((TEMPLATE_ROOT / "cases").glob("*.json"))
    if len(cases) < 2:
        fail("模板至少需要两组参数实例")

    checked: list[tuple[str, dict[str, object]]] = []
    for case_path in cases:
        config = normalize_config(json.loads(case_path.read_text(encoding="utf-8")))
        model = assert_physics(config, derive_physics(config))
        assertions = physics_assertions(config, model)
        failed = [name for name, passed in assertions.items() if not passed]
        if failed:
            fail(f"{case_path.name} 物理断言失败：{', '.join(failed)}")
        checked.append((case_path.stem, model))
    return checked


def validate_all_direction_combinations(base_config: dict[str, object]) -> None:
    for motion_direction in ("left", "right"):
        for field_direction in ("into_page", "out_of_page"):
            config = copy.deepcopy(base_config)
            config["motion_direction"] = motion_direction
            config["field_direction"] = field_direction
            model = assert_physics(config, derive_physics(config))
            expected_motion = 1 if motion_direction == "right" else -1
            expected_field = 1 if field_direction == "out_of_page" else -1
            if model["current_sign"] != -expected_motion * expected_field:
                fail(f"方向组合 {motion_direction}/{field_direction} 的电流方向错误")
            if model["force_sign"] != -expected_motion:
                fail(f"方向组合 {motion_direction}/{field_direction} 的安培力未阻碍运动")


def expect_rejected(config: dict[str, object], expected_fragment: str) -> None:
    try:
        normalize_config(config)
    except ModelValidationError as error:
        if expected_fragment not in str(error):
            fail(f"拒绝原因不符：{error}")
    else:
        fail(f"非法配置未被拒绝：应包含 {expected_fragment}")


def validate_scope_rejections(base_config: dict[str, object]) -> None:
    negative_field = copy.deepcopy(base_config)
    negative_field["magnetic_field_t"] = -0.2
    expect_rejected(negative_field, "超出模板范围")

    unsupported_direction = copy.deepcopy(base_config)
    unsupported_direction["motion_direction"] = "rotate"
    expect_rejected(unsupported_direction, "只允许 left 或 right")

    executable_payload = copy.deepcopy(base_config)
    executable_payload["physics_code"] = "E = custom_model()"
    expect_rejected(executable_payload, "不允许的字段")


def validate_rendered_pages() -> None:
    result = subprocess.run(
        [sys.executable, str(TEMPLATE_ROOT / "render_examples.py"), "--check"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        fail(result.stdout.strip() or result.stderr.strip() or "模板实例检查失败")

    required_fragments = (
        'id="scene"',
        'id="timeRange"',
        'id="speedRange"',
        'id="coursewareConfig"',
        'id="lockedModel"',
        "model.forceSign === -model.motionSign",
    )
    pages = sorted((TEMPLATE_ROOT / "examples").glob("*/index.html"))
    if len(pages) < 2:
        fail("未找到两组落盘示例页面")
    for page in pages:
        source = page.read_text(encoding="utf-8")
        if "__CONFIG_JSON__" in source or "__MODEL_JSON__" in source:
            fail(f"{page} 存在未替换模板标记")
        missing = [fragment for fragment in required_fragments if fragment not in source]
        if missing:
            fail(f"{page} 缺少模板结构：{', '.join(missing)}")


def main() -> int:
    checked = validate_examples()
    base_config = normalize_config(
        json.loads((TEMPLATE_ROOT / "cases" / "rightward-into.json").read_text(encoding="utf-8"))
    )
    validate_all_direction_combinations(base_config)
    validate_scope_rejections(base_config)
    validate_rendered_pages()

    print(f"生成器模板校验通过：{len(checked)} 组实例，4 组方向组合，3 组越界拒绝。")
    for name, model in checked:
        print(
            f"- {name}: E={model['emf_v']:.3f} V, I={model['current_a']:.3f} A, "
            f"F={model['magnetic_force_n']:.3f} N, P={model['joule_power_w']:.3f} W, "
            f"电流{model['rod_current_label']}，安培力{model['force_label']}"
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, ModelValidationError, OSError, json.JSONDecodeError) as error:
        print(f"生成器模板校验失败：{error}", file=sys.stderr)
        raise SystemExit(1)
