"""Execute generated pure-physics JavaScript in a constrained Node VM."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable

from research.generation.harness.assertions import AssertionReport
from research.generation.harness.contracts import FORBIDDEN_CODE, ContractError


HERE = Path(__file__).resolve().parent
NODE_RUNNER = HERE / "node_runner.js"


class SandboxError(RuntimeError):
    pass


def execute_model(code: str, model_input: dict[str, Any], timeout: float = 3.0) -> dict[str, Any]:
    if not isinstance(code, str) or FORBIDDEN_CODE.search(code):
        raise SandboxError("生成代码包含沙箱禁止能力")
    node = shutil.which("node")
    if not node:
        raise SandboxError("系统缺少 Node.js，无法运行 JavaScript 沙箱")
    request = json.dumps({"code": code, "input": model_input}, ensure_ascii=False).encode("utf-8")
    try:
        completed = subprocess.run(
            [node, "--max-old-space-size=64", str(NODE_RUNNER)],
            input=request,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
            cwd=str(HERE),
            env={"PATH": os.path.dirname(node)},
        )
    except subprocess.TimeoutExpired as error:
        raise SandboxError("生成代码执行超时") from error
    try:
        response = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise SandboxError("沙箱未返回有效 JSON") from error
    if completed.returncode != 0 or response.get("ok") is not True:
        raise SandboxError(f"生成代码执行失败：{response.get('error', 'unknown error')}")
    output = response.get("output")
    if not isinstance(output, dict):
        raise SandboxError("生成代码 sample() 必须返回 JSON 对象")
    return output


def validate_in_sandbox(
    code: str,
    model_input: dict[str, Any],
    validator: Callable[[dict[str, Any], dict[str, Any]], AssertionReport],
) -> tuple[dict[str, Any], AssertionReport]:
    scenario = model_input.get("scenario")
    if not isinstance(scenario, dict):
        raise ContractError("沙箱输入缺少老师确认的 scenario")
    output = execute_model(code, model_input)
    axis = model_input.get("times_s", model_input.get("angles_rad"))
    assertion_report = validator(scenario, output, axis)
    assertion_report.require()
    return output, assertion_report
