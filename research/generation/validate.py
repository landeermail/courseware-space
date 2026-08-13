#!/usr/bin/env python3
"""Validate generator templates without changing the existing site validator."""

from __future__ import annotations

import copy
import json
import math
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_ROOT = Path(__file__).resolve().parent
TEMPLATE_ROOT = MODULE_ROOT / "templates" / "conducting-rod"
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


def validate_result_page(result: dict[str, object]) -> None:
    output_path = result.get("output_path")
    if not isinstance(output_path, str) or not output_path:
        fail(f"{result.get('id')} 缺少生成产物路径")
    legacy_path = Path(output_path)
    try:
        legacy_path = legacy_path.relative_to("generator")
    except ValueError:
        pass
    page = MODULE_ROOT / "evidence" / "legacy" / legacy_path
    if not page.is_file():
        fail(f"生成产物不存在：{output_path}")
    source = page.read_text(encoding="utf-8")
    if 'id="scene"' not in source or 'id="lockedModel"' not in source:
        fail(f"生成产物不是可交互锁定模板：{output_path}")


def validate_expected_parameters(results: list[dict[str, object]], fixture_name: str) -> int:
    fixtures = json.loads((MODULE_ROOT / "fixtures" / fixture_name).read_text(encoding="utf-8"))
    expected_by_id = {item["id"]: item.get("expected") for item in fixtures if item.get("expected")}
    result_by_id = {item.get("id"): item for item in results}
    if set(result_by_id) != set(expected_by_id):
        fail(f"{fixture_name} 的题目 ID 与证据不一致")
    checked = 0
    for case_id, expected in expected_by_id.items():
        config = result_by_id[case_id].get("config")
        if not isinstance(config, dict) or not isinstance(expected, dict):
            fail(f"{case_id} 缺少可对照参数")
        for key, expected_value in expected.items():
            actual = config.get(key)
            if isinstance(expected_value, (int, float)) and not isinstance(expected_value, bool):
                if not isinstance(actual, (int, float)) or not math.isclose(
                    float(actual), float(expected_value), rel_tol=1e-12, abs_tol=1e-12
                ):
                    fail(f"{case_id} 参数 {key} 提取错误：{actual} != {expected_value}")
            elif actual != expected_value:
                fail(f"{case_id} 参数 {key} 提取错误：{actual} != {expected_value}")
        checked += 1
    return checked


def validate_acceptance_evidence() -> tuple[int, int, int, int, int]:
    task2 = json.loads((MODULE_ROOT / "evidence" / "legacy" / "task2" / "results.json").read_text(encoding="utf-8"))
    in_scope = task2.get("in_scope")
    out_scope = task2.get("out_of_scope")
    if not isinstance(in_scope, list) or len(in_scope) != 5:
        fail("任务 2 必须保留 5 道范围内题")
    if not isinstance(out_scope, list) or len(out_scope) != 3:
        fail("任务 2 必须保留 3 道范围外题")
    if any(result.get("status") != "succeeded" for result in in_scope):
        fail("任务 2 范围内题没有全部生成成功")
    if any(result.get("status") != "manual_required" for result in out_scope):
        fail("任务 2 范围外题没有全部转人工")
    for result in in_scope:
        validate_result_page(result)
    expected_checked = validate_expected_parameters(in_scope, "task2-in-scope.json")
    corruption = task2.get("corruption")
    if not isinstance(corruption, dict) or not str(corruption.get("red", "")).startswith("RED："):
        fail("任务 2 缺少错误参数红色证据")
    if not str(corruption.get("green", "")).startswith("GREEN："):
        fail("任务 2 缺少安全兜底绿色证据")

    benchmark = json.loads(
        (MODULE_ROOT / "evidence" / "legacy" / "benchmark" / "results.json").read_text(encoding="utf-8")
    )
    results = benchmark.get("results")
    if not isinstance(results, list) or len(results) != 20:
        fail("任务 3 必须保留 20 道基准题")
    if any(result.get("attempt") != 1 for result in results):
        fail("任务 3 每道题必须只有一次生成尝试")
    successful = sum(result.get("status") == "succeeded" for result in results)
    declared_successful = benchmark.get("successful")
    declared_rate = benchmark.get("success_rate")
    if declared_successful != successful or not isinstance(declared_rate, (int, float)):
        fail("任务 3 汇总与逐题结果不一致")
    if abs(float(declared_rate) - successful / 20) > 1e-12:
        fail("任务 3 成功率计算错误")
    if float(declared_rate) < 0.60:
        fail("任务 3 一次成功率低于 60%")
    for result in results:
        if result.get("status") == "succeeded":
            validate_result_page(result)
        if not result.get("source"):
            fail(f"{result.get('id')} 缺少题目来源")
    expected_checked += validate_expected_parameters(results, "benchmark-20.json")
    return len(in_scope), len(out_scope), successful, len(results), expected_checked


def validate_product_surface() -> None:
    generator_page = (MODULE_ROOT / "generator" / "index.html").read_text(encoding="utf-8")
    for fragment in ('id="generateForm"', 'id="statusPanel"', 'id="resultPanel"', 'id="manualForm"'):
        if fragment not in generator_page:
            fail(f"生成器页面缺少结构：{fragment}")
    homepage = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
    if '"path": "generator/"' in homepage:
        fail("公开首页不得包含本地生成器入口")
    for path in (
        MODULE_ROOT / "app.py",
        MODULE_ROOT / "runtime" / "generator_service.py",
        MODULE_ROOT / "runtime" / "kimi_client.py",
    ):
        if not path.is_file():
            fail(f"生成服务文件缺失：{path.relative_to(ROOT)}")
    secret_marker = "sk-" + "kimi-"
    for base in (MODULE_ROOT / "runtime", MODULE_ROOT / "generator", MODULE_ROOT / "templates"):
        for path in base.rglob("*"):
            if path.is_file() and secret_marker in path.read_text(encoding="utf-8", errors="ignore"):
                fail(f"发现疑似落盘 API Key：{path.relative_to(ROOT)}")


def main() -> int:
    checked = validate_examples()
    base_config = normalize_config(
        json.loads((TEMPLATE_ROOT / "cases" / "rightward-into.json").read_text(encoding="utf-8"))
    )
    validate_all_direction_combinations(base_config)
    validate_scope_rejections(base_config)
    validate_rendered_pages()
    task2_in, task2_out, benchmark_success, benchmark_total, expected_checked = validate_acceptance_evidence()
    validate_product_surface()

    print(f"生成器模板校验通过：{len(checked)} 组实例，4 组方向组合，3 组越界拒绝。")
    for name, model in checked:
        print(
            f"- {name}: E={model['emf_v']:.3f} V, I={model['current_a']:.3f} A, "
            f"F={model['magnetic_force_n']:.3f} N, P={model['joule_power_w']:.3f} W, "
            f"电流{model['rod_current_label']}，安培力{model['force_label']}"
        )
    print(
        f"生成管线证据通过：任务2范围内 {task2_in}/5、范围外 {task2_out}/3；"
        f"任务3一次成功率 {benchmark_success}/{benchmark_total}；参数对照 {expected_checked}/25。"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, ModelValidationError, OSError, json.JSONDecodeError) as error:
        print(f"生成器模板校验失败：{error}", file=sys.stderr)
        raise SystemExit(1)
