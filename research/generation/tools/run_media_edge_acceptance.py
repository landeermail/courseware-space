#!/usr/bin/env python3
"""Run low-confidence, one-page PDF, and reversed-field red/green acceptance."""

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
from research.generation.runtime.media_service import MediaConfirmationWorkflow, MediaError, MediaParser  # noqa: E402


EVIDENCE_ROOT = MODULE_ROOT / "evidence" / "legacy" / "media-inputs"
RUNTIME_ROOT = MODULE_ROOT / "evidence" / "legacy" / "media-runtime-edge"
RESULTS_PATH = EVIDENCE_ROOT / "edge-results.json"
IMAGE_01_PARAMETERS = {
    "magnetic_field_t": 0.5,
    "rod_length_m": 1.0,
    "rod_speed_m_s": 2.0,
    "resistance_ohm": 0.4,
    "field_direction": "into_page",
    "motion_direction": "right",
}


def encoded(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")


def wait_for_job(manager: GenerationManager, job_id: str) -> dict[str, Any]:
    for _ in range(100):
        job = manager.get(job_id)
        if job and job["status"] in {"succeeded", "manual_required"}:
            return job
        time.sleep(0.05)
    raise RuntimeError(f"生成任务超时：{job_id}")


class StaticParser:
    def __init__(self, parsed: dict[str, Any]) -> None:
        self.parsed = parsed

    def parse(self, filename: object, mime_type: object, data_base64: object) -> dict[str, Any]:
        return json.loads(json.dumps(self.parsed, ensure_ascii=False))


def main() -> int:
    if RESULTS_PATH.exists():
        print(f"拒绝重跑：验收结果已存在 {RESULTS_PATH.relative_to(MODULE_ROOT)}")
        return 2
    client = KimiCodeClient()
    if not client.configured:
        print("缺少 KIMI_API_KEY")
        return 2
    parser = MediaParser(client)
    recorder = ManualRequestRecorder(RUNTIME_ROOT / "manual-requests.jsonl")
    manager = GenerationManager(GenerationService(client, recorder), RUNTIME_ROOT)
    uncertain_records: list[dict[str, Any]] = []
    try:
        for index in range(1, 4):
            path = EVIDENCE_ROOT / f"uncertain-{index:02d}.png"
            parsed = parser.parse(path.name, "image/png", encoded(path))
            ready_count = sum(bool(item["ready_for_confirmation"]) for item in parsed["questions"])
            if parsed["status"] != "needs_input" or ready_count:
                raise RuntimeError(f"{path.name} 未被确认闸拦截")
            uncertain_records.append(
                {
                    "sample_id": path.stem,
                    "status": parsed["status"],
                    "message": parsed["message"],
                    "confidence": min(item["confidence"] for item in parsed["questions"]),
                    "supported": all(item["supported"] for item in parsed["questions"]),
                    "reasons": [item["reason"] for item in parsed["questions"]],
                    "ready_count": ready_count,
                }
            )
            print(f'{path.stem}: confidence={uncertain_records[-1]["confidence"]:.2f}, needs_input=ok')

        pdf_path = EVIDENCE_ROOT / "multi-question.pdf"
        pdf_parsed = parser.parse(pdf_path.name, "application/pdf", encoded(pdf_path))
        if pdf_parsed["page_count"] != 1 or len(pdf_parsed["questions"]) != 2:
            raise RuntimeError(
                f'PDF 切分结果异常：pages={pdf_parsed["page_count"]}, questions={len(pdf_parsed["questions"])}'
            )
        first = next(
            (
                question
                for question in pdf_parsed["questions"]
                if question["parameters"].get("magnetic_field_t") == 0.5
            ),
            None,
        )
        if first is None or not first["supported"]:
            raise RuntimeError("PDF 第 1 题没有被可靠识别为模板范围内")
        pdf_workflow = MediaConfirmationWorkflow(StaticParser(pdf_parsed), manager)  # type: ignore[arg-type]
        pdf_session = pdf_workflow.parse_upload(pdf_path.name, "application/pdf", "not-retained")
        pdf_submission = pdf_workflow.confirm_and_submit(
            {
                "parse_id": pdf_session["id"],
                "question_id": first["id"],
                "teacher_confirmed": True,
                "question_text": first["question_text"],
                "parameters": IMAGE_01_PARAMETERS,
                "current_direction": "d_to_c",
                "asks": ["求感应电动势大小", "判断杆中电流方向"],
            }
        )
        pdf_job = wait_for_job(manager, pdf_submission["job"]["id"])
        if pdf_job["status"] != "succeeded":
            raise RuntimeError("PDF 选题确认后生成失败")
        print("multi-question.pdf: page=1, questions=2, selected_generation=ok")

        faulty_question = {
            "id": "p1-q1",
            "page": 1,
            "question_text": "闭合平行导轨间距1.00 m，0.50 T匀强磁场垂直纸面向里，杆以2.00 m/s向右匀速运动，总电阻0.40 Ω，求电动势和电流方向。",
            "confidence": 0.99,
            "supported": True,
            "reason": "",
            "parameters": {**IMAGE_01_PARAMETERS, "field_direction": "out_of_page"},
            "current_direction": "d_to_c",
            "asks": ["求感应电动势", "判断电流方向"],
            "ready_for_confirmation": True,
        }
        faulty_parse = {
            "source_input_type": "image",
            "filename": "fault-injected.png",
            "page_count": 1,
            "confidence_threshold": 0.75,
            "status": "awaiting_confirmation",
            "message": "故障注入：AI 将磁场方向读反。",
            "questions": [faulty_question],
        }
        fault_workflow = MediaConfirmationWorkflow(StaticParser(faulty_parse), manager)  # type: ignore[arg-type]
        fault_session = fault_workflow.parse_upload("fault-injected.png", "image/png", "not-retained")
        red_error = ""
        try:
            fault_workflow.confirm_and_submit(
                {
                    "parse_id": fault_session["id"],
                    "question_id": "p1-q1",
                    "teacher_confirmed": True,
                    "question_text": faulty_question["question_text"],
                    "parameters": faulty_question["parameters"],
                    "current_direction": faulty_question["current_direction"],
                    "asks": faulty_question["asks"],
                }
            )
        except MediaError as error:
            red_error = str(error)
        if "不一致" not in red_error:
            raise RuntimeError("磁场读反的红灯验证没有被后端拦截")
        green_submission = fault_workflow.confirm_and_submit(
            {
                "parse_id": fault_session["id"],
                "question_id": "p1-q1",
                "teacher_confirmed": True,
                "question_text": faulty_question["question_text"],
                "parameters": IMAGE_01_PARAMETERS,
                "current_direction": "d_to_c",
                "asks": faulty_question["asks"],
            }
        )
        green_job = wait_for_job(manager, green_submission["job"]["id"])
        if green_job["status"] != "succeeded" or green_job["config"]["field_direction"] != "into_page":
            raise RuntimeError("老师修正后的绿灯验证失败")
        print("fault-injection: reversed-field=blocked, teacher-correction=generated")
    finally:
        manager.close()

    result = {
        "acceptance": "media-edge-cases-v1",
        "run_at": datetime.now(timezone.utc).isoformat(),
        "model": client.model,
        "uncertain_samples": uncertain_records,
        "pdf": {
            "path": str((EVIDENCE_ROOT / "multi-question.pdf").relative_to(MODULE_ROOT)),
            "page_count": pdf_parsed["page_count"],
            "question_count": len(pdf_parsed["questions"]),
            "question_ids": [item["id"] for item in pdf_parsed["questions"]],
            "selected_job_status": pdf_job["status"],
            "selected_output_path": str(
                (RUNTIME_ROOT / "generated" / pdf_job["id"] / "index.html").relative_to(MODULE_ROOT)
            ),
        },
        "reverse_field_red_green": {
            "ai_field_direction": "out_of_page",
            "ai_current_direction": "d_to_c",
            "red_status": "blocked",
            "red_reason": red_error,
            "teacher_field_direction": "into_page",
            "teacher_current_direction": "d_to_c",
            "green_status": green_job["status"],
            "green_final_field_direction": green_job["config"]["field_direction"],
            "green_output_path": str(
                (RUNTIME_ROOT / "generated" / green_job["id"] / "index.html").relative_to(MODULE_ROOT)
            ),
        },
    }
    RESULTS_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("边界验收完成：3/3 不确定样本拦截，PDF 1 页 2 题切分，反向磁场红→绿通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
