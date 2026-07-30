#!/usr/bin/env python3
"""Run real Kimi acceptance suites and preserve inspectable evidence."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SERVER_DIR = Path(__file__).resolve().parent
ROOT = SERVER_DIR.parent
sys.path.insert(0, str(SERVER_DIR))

from generator_service import (  # noqa: E402
    GenerationService,
    ManualRequestRecorder,
    PROMPT_SHA256,
    PROMPT_VERSION,
    build_template_config,
    parse_ai_response,
)
from kimi_client import KimiCodeClient  # noqa: E402


class FixedClient:
    def __init__(self, response: str) -> None:
        self.response = response

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        return self.response


def load_fixture(name: str) -> list[dict[str, Any]]:
    return json.loads((SERVER_DIR / "fixtures" / name).read_text(encoding="utf-8"))


def run_cases(
    cases: list[dict[str, Any]],
    service: GenerationService,
    output_root: Path,
) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    for index, case in enumerate(cases, start=1):
        output_dir = output_root / case["id"]
        outcome = service.generate_sync(case["question"], output_dir, request_id=case["id"])
        expected = case.get("expected")
        matches_expected = True
        if isinstance(expected, dict):
            matches_expected = outcome.config is not None and all(
                outcome.config.get(key) == value for key, value in expected.items()
            )
        result = {
            "id": case["id"],
            "source": case["source"],
            "attempt": 1,
            "matches_expected": matches_expected,
            **asdict(outcome),
        }
        if not matches_expected:
            result["status"] = "parameter_mismatch"
            result["reason"] = "AI 提取参数与题库预期不一致"
        results.append(result)
        print(f"[{index}/{len(cases)}] {case['id']}: {outcome.status}{' - ' + outcome.reason if outcome.reason else ''}")
    return results


def corrupted_parameter_evidence(evidence_dir: Path) -> dict[str, str]:
    corrupt_response = json.dumps(
        {
            "supported": True,
            "reason": "",
            "parameters": {
                "magnetic_field_t": 0.5,
                "rod_length_m": 1.0,
                "rod_speed_m_s": 2.0,
                "resistance_ohm": -0.4,
                "field_direction": "into_page",
                "motion_direction": "right",
            },
        },
        ensure_ascii=False,
    )
    question = "闭合平行导轨间距1 m，0.5 T匀强磁场向里，杆以2 m/s向右匀速运动，总电阻0.4 Ω。"
    _, _, parameters = parse_ai_response(corrupt_response)
    assert parameters is not None
    try:
        build_template_config(question, parameters)
    except Exception as error:
        red = f"RED：锁定模板拒绝错误参数：{error}"
    else:
        raise AssertionError("错误参数没有触发模板校验")

    recorder = ManualRequestRecorder(evidence_dir / "corrupt-manual.jsonl")
    service = GenerationService(FixedClient(corrupt_response), recorder)  # type: ignore[arg-type]
    outcome = service.generate_sync(question, evidence_dir / "corrupt-output", request_id="corrupt-parameter")
    if outcome.status != "manual_required":
        raise AssertionError("错误参数未转入人工兜底")
    green = f"GREEN：生成管线状态={outcome.status}，已写入人工待处理清单"
    print(red)
    print(green)
    return {"red": red, "green": green}


def write_evidence(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_task2() -> int:
    evidence_dir = SERVER_DIR / "evidence" / "task2"
    service = GenerationService(
        KimiCodeClient(),
        ManualRequestRecorder(evidence_dir / "manual-requests.jsonl"),
    )
    in_scope = run_cases(
        load_fixture("task2-in-scope.json"),
        service,
        ROOT / "generator" / "generated" / "task2",
    )
    out_scope = run_cases(
        load_fixture("task2-out-of-scope.json"),
        service,
        evidence_dir / "unexpected-output",
    )
    corruption = corrupted_parameter_evidence(evidence_dir)
    payload = {
        "suite": "task2",
        "ran_at": datetime.now(timezone.utc).isoformat(),
        "prompt_version": PROMPT_VERSION,
        "prompt_sha256": PROMPT_SHA256,
        "in_scope": in_scope,
        "out_of_scope": out_scope,
        "corruption": corruption,
    }
    write_evidence(evidence_dir / "results.json", payload)
    successful = sum(item["status"] == "succeeded" for item in in_scope)
    fallback = sum(item["status"] == "manual_required" for item in out_scope)
    print(f"任务2汇总：范围内 {successful}/5 生成成功；范围外 {fallback}/3 转人工。")
    return 0 if successful == 5 and fallback == 3 else 1


def run_benchmark() -> int:
    evidence_dir = SERVER_DIR / "evidence" / "benchmark"
    evidence_path = evidence_dir / "results.json"
    if evidence_path.exists():
        print("基准结果已存在；为保护一次成功率证据，拒绝重复运行。", file=sys.stderr)
        return 2
    service = GenerationService(
        KimiCodeClient(),
        ManualRequestRecorder(evidence_dir / "manual-requests.jsonl"),
    )
    results = run_cases(
        load_fixture("benchmark-20.json"),
        service,
        ROOT / "generator" / "generated" / "benchmark",
    )
    successful = sum(item["status"] == "succeeded" for item in results)
    rate = successful / len(results)
    payload = {
        "suite": "benchmark-20",
        "ran_at": datetime.now(timezone.utc).isoformat(),
        "prompt_version": PROMPT_VERSION,
        "prompt_sha256": PROMPT_SHA256,
        "successful": successful,
        "total": len(results),
        "success_rate": rate,
        "results": results,
    }
    write_evidence(evidence_path, payload)
    print(f"任务3一次成功率：{successful}/{len(results)} = {rate:.0%}")
    return 0 if rate >= 0.60 else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("suite", choices=("task2", "benchmark"))
    args = parser.parse_args()
    if not os.environ.get("KIMI_API_KEY"):
        print("缺少 KIMI_API_KEY", file=sys.stderr)
        return 2
    return run_task2() if args.suite == "task2" else run_benchmark()


if __name__ == "__main__":
    raise SystemExit(main())
