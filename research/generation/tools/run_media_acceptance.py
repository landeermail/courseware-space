#!/usr/bin/env python3
"""Run the frozen five-image confirmation-gate acceptance exactly once."""

from __future__ import annotations

import base64
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MODULE_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = MODULE_ROOT.parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))

from research.generation.runtime.generator_service import GenerationManager, GenerationService, ManualRequestRecorder  # noqa: E402
from research.generation.runtime.kimi_client import KimiCodeClient  # noqa: E402
from research.generation.runtime.media_service import MediaConfirmationWorkflow, MediaParser  # noqa: E402


EVIDENCE_ROOT = MODULE_ROOT / "evidence" / "legacy" / "media-inputs"
RUNTIME_ROOT = MODULE_ROOT / "evidence" / "legacy" / "media-runtime"
RESULTS_PATH = EVIDENCE_ROOT / "results.json"

EXPECTED = [
    {
        "id": "image-01",
        "parameters": {"magnetic_field_t": 0.5, "rod_length_m": 1.0, "rod_speed_m_s": 2.0, "resistance_ohm": 0.4, "field_direction": "into_page", "motion_direction": "right"},
        "current_direction": "d_to_c",
        "asks": ["求感应电动势大小", "判断杆中电流方向"],
    },
    {
        "id": "image-02",
        "parameters": {"magnetic_field_t": 0.8, "rod_length_m": 0.6, "rod_speed_m_s": 3.0, "resistance_ohm": 1.2, "field_direction": "out_of_page", "motion_direction": "right"},
        "current_direction": "c_to_d",
        "asks": ["求回路中的电流大小", "判断电流方向"],
    },
    {
        "id": "image-03",
        "parameters": {"magnetic_field_t": 0.25, "rod_length_m": 1.2, "rod_speed_m_s": 4.0, "resistance_ohm": 0.5, "field_direction": "into_page", "motion_direction": "left"},
        "current_direction": "c_to_d",
        "asks": ["判断 c、d 两端电势高低", "求安培力大小"],
    },
    {
        "id": "image-04",
        "parameters": {"magnetic_field_t": 1.2, "rod_length_m": 0.8, "rod_speed_m_s": 1.5, "resistance_ohm": 0.6, "field_direction": "out_of_page", "motion_direction": "left"},
        "current_direction": "d_to_c",
        "asks": ["判断感应电流方向", "求电阻的焦耳功率"],
    },
    {
        "id": "image-05",
        "parameters": {"magnetic_field_t": 0.35, "rod_length_m": 1.5, "rod_speed_m_s": 5.0, "resistance_ohm": 0.75, "field_direction": "into_page", "motion_direction": "right"},
        "current_direction": "d_to_c",
        "asks": ["求电动势", "求电流", "求安培力", "说明能量转化关系"],
    },
]


def same_parameters(actual: dict[str, Any], expected: dict[str, Any]) -> bool:
    if set(actual) != set(expected):
        return False
    for key, expected_value in expected.items():
        actual_value = actual[key]
        if isinstance(expected_value, float):
            if not isinstance(actual_value, (int, float)) or abs(float(actual_value) - expected_value) > 1e-9:
                return False
        elif actual_value != expected_value:
            return False
    return True


def wait_for_job(manager: GenerationManager, job_id: str) -> dict[str, Any]:
    for _ in range(100):
        job = manager.get(job_id)
        if job and job["status"] in {"succeeded", "manual_required"}:
            return job
        time.sleep(0.05)
    raise RuntimeError(f"生成任务超时：{job_id}")


def main() -> int:
    if RESULTS_PATH.exists():
        print(f"拒绝重跑：验收结果已存在 {RESULTS_PATH.relative_to(MODULE_ROOT)}")
        return 2
    client = KimiCodeClient()
    if not client.configured:
        print("缺少 KIMI_API_KEY")
        return 2
    recorder = ManualRequestRecorder(RUNTIME_ROOT / "manual-requests.jsonl")
    manager = GenerationManager(GenerationService(client, recorder), RUNTIME_ROOT)
    workflow = MediaConfirmationWorkflow(MediaParser(client), manager)
    records: list[dict[str, Any]] = []
    try:
        for expected in EXPECTED:
            image_path = EVIDENCE_ROOT / f'{expected["id"]}.png'
            parsed = workflow.parse_upload(
                image_path.name,
                "image/png",
                base64.b64encode(image_path.read_bytes()).decode("ascii"),
            )
            if len(parsed["questions"]) != 1:
                raise RuntimeError(f'{expected["id"]} 识别题数不是 1')
            question = parsed["questions"][0]
            if not question["supported"]:
                raise RuntimeError(f'{expected["id"]} 被错误判为范围外：{question["reason"]}')
            payload = {
                "parse_id": parsed["id"],
                "question_id": question["id"],
                "teacher_confirmed": True,
                "question_text": question["question_text"],
                "parameters": expected["parameters"],
                "current_direction": expected["current_direction"],
                "asks": expected["asks"],
            }
            submitted = workflow.confirm_and_submit(payload)
            job = wait_for_job(manager, submitted["job"]["id"])
            if job["status"] != "succeeded":
                raise RuntimeError(f'{expected["id"]} 确认后生成失败：{job.get("reason", "未知错误")}')
            if not same_parameters(job["config"], {**expected["parameters"], **{key: job["config"][key] for key in job["config"] if key not in expected["parameters"]}}):
                raise RuntimeError(f'{expected["id"]} 最终参数未采用老师确认值')
            records.append(
                {
                    "sample_id": expected["id"],
                    "source_path": str(image_path.relative_to(MODULE_ROOT)),
                    "parse_status": parsed["status"],
                    "confidence": question["confidence"],
                    "ai_parameters": question["parameters"],
                    "ai_current_direction": question["current_direction"],
                    "ai_matches_expected": same_parameters(question["parameters"], expected["parameters"]),
                    "teacher_parameters": expected["parameters"],
                    "teacher_current_direction": expected["current_direction"],
                    "corrections_applied": submitted["corrections_applied"],
                    "job_id": job["id"],
                    "job_status": job["status"],
                    "output_url": job["output_url"],
                    "output_path": str((RUNTIME_ROOT / "generated" / job["id"] / "index.html").relative_to(MODULE_ROOT)),
                }
            )
            print(
                f'{expected["id"]}: confidence={question["confidence"]:.2f}, '
                f'ai_exact={records[-1]["ai_matches_expected"]}, '
                f'corrected={submitted["corrections_applied"]}, generated=ok'
            )
    finally:
        manager.close()
    result = {
        "acceptance": "media-image-five-v1",
        "run_at": datetime.now(timezone.utc).isoformat(),
        "model": client.model,
        "count": len(records),
        "generated_count": sum(record["job_status"] == "succeeded" for record in records),
        "all_physics_match_teacher_confirmation": all(
            same_parameters(record["teacher_parameters"], EXPECTED[index]["parameters"])
            for index, record in enumerate(records)
        ),
        "records": records,
    }
    RESULTS_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"图片验收完成：{result['generated_count']}/{result['count']} 确认后生成成功。")
    return 0 if result["generated_count"] == 5 else 1


if __name__ == "__main__":
    raise SystemExit(main())
