#!/usr/bin/env python3
"""Run the locked v2 acceptance suites against the deployed public JSON API once."""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen


SERVER_DIR = Path(__file__).resolve().parent
ROOT = SERVER_DIR.parent
FIXTURE_DIR = SERVER_DIR / "fixtures"
MEDIA_DIR = SERVER_DIR / "evidence" / "media-inputs"
RESULTS_PATH = SERVER_DIR / "evidence" / "cloud-v2" / "results.json"
DEFAULT_ORIGIN = "https://landeermail.github.io"

sys.path.insert(0, str(SERVER_DIR))
from run_media_acceptance import EXPECTED as MEDIA_EXPECTED  # noqa: E402


class PublicApi:
    def __init__(self, base_url: str, origin: str, access_code: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.origin = origin
        self.access_code = access_code

    def json(self, path: str, payload: dict[str, Any] | None = None, timeout: int = 190) -> dict[str, Any]:
        body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = Request(
            f"{self.base_url}{path}",
            data=body,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Origin": self.origin,
                "X-Courseware-Access-Code": self.access_code,
            },
            method="GET" if payload is None else "POST",
        )
        try:
            with urlopen(request, timeout=timeout) as response:
                data = json.loads(response.read())
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            try:
                message = json.loads(detail).get("error", detail)
            except json.JSONDecodeError:
                message = detail
            raise RuntimeError(f"HTTP {error.code}: {message}") from error
        if not isinstance(data, dict):
            raise RuntimeError("公网 API 未返回 JSON 对象")
        return data

    def expect_error(self, path: str, payload: dict[str, Any], expected_text: str) -> str:
        try:
            self.json(path, payload)
        except RuntimeError as error:
            message = str(error)
            if expected_text not in message:
                raise
            return message
        raise RuntimeError("预期请求被后端拒绝，但实际已放行")

    def wait_job(self, job_id: str) -> dict[str, Any]:
        for _ in range(180):
            job = self.json(f"/api/jobs/{job_id}").get("job")
            if isinstance(job, dict) and job.get("status") in {"succeeded", "manual_required"}:
                return job
            time.sleep(1)
        raise RuntimeError(f"公网生成任务超时：{job_id}")

    def output_is_html(self, output_url: object) -> bool:
        if not isinstance(output_url, str) or not output_url.startswith("https://"):
            return False
        with urlopen(Request(output_url, headers={"Range": "bytes=0-4095"}), timeout=30) as response:
            content = response.read(4096).decode("utf-8", errors="replace")
        lowered = content.lower()
        return "<html" in lowered and "<title>" in lowered


def load_fixture(name: str) -> list[dict[str, Any]]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def parameters_match(actual: object, expected: dict[str, Any]) -> bool:
    if not isinstance(actual, dict):
        return False
    for key, expected_value in expected.items():
        value = actual.get(key)
        if isinstance(expected_value, float):
            if not isinstance(value, (int, float)) or abs(float(value) - expected_value) > 1e-9:
                return False
        elif value != expected_value:
            return False
    return True


def run_text_cases(api: PublicApi, cases: list[dict[str, Any]], expect_success: bool) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for index, case in enumerate(cases, 1):
        record: dict[str, Any] = {"id": case["id"], "source": case["source"], "attempt": 1}
        try:
            job_id = api.json("/api/generate", {"question": case["question"]})["job"]["id"]
            job = api.wait_job(job_id)
            record.update(
                {
                    "job_id": job_id,
                    "status": job.get("status"),
                    "reason": job.get("reason"),
                    "output_url": job.get("output_url"),
                    "parameters_match_expected": parameters_match(job.get("config"), case["expected"])
                    if "expected" in case
                    else None,
                    "output_opened_as_html": api.output_is_html(job.get("output_url"))
                    if job.get("status") == "succeeded"
                    else False,
                }
            )
        except Exception as error:  # Keep first-attempt evidence instead of rerunning failed cases.
            record.update({"status": "request_failed", "reason": str(error), "output_opened_as_html": False})
        expected_status = "succeeded" if expect_success else "manual_required"
        record["accepted"] = record.get("status") == expected_status and (
            not expect_success
            or (record.get("parameters_match_expected") is True and record.get("output_opened_as_html") is True)
        )
        records.append(record)
        print(f"[{index}/{len(cases)}] {case['id']}: {record['status']} accepted={record['accepted']}", flush=True)
    return records


def upload_payload(path: Path, mime_type: str) -> dict[str, str]:
    return {
        "filename": path.name,
        "mime_type": mime_type,
        "data_base64": base64.b64encode(path.read_bytes()).decode("ascii"),
    }


def confirmation_payload(parsed: dict[str, Any], expected: dict[str, Any]) -> dict[str, Any]:
    question = parsed["questions"][0]
    return {
        "parse_id": parsed["id"],
        "question_id": question["id"],
        "teacher_confirmed": True,
        "question_text": question["question_text"],
        "parameters": expected["parameters"],
        "current_direction": expected["current_direction"],
        "asks": expected["asks"],
    }


def run_media(api: PublicApi) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    records: list[dict[str, Any]] = []
    red_green: dict[str, Any] = {}
    for index, expected in enumerate(MEDIA_EXPECTED, 1):
        path = MEDIA_DIR / f"{expected['id']}.png"
        try:
            parsed = api.json("/api/media/parse", upload_payload(path, "image/png"))["parse"]
            payload = confirmation_payload(parsed, expected)
            if index == 1:
                wrong = {**payload, "current_direction": "c_to_d"}
                red_reason = api.expect_error("/api/media/confirm", wrong, "电流方向")
            submission = api.json("/api/media/confirm", payload)
            job = api.wait_job(submission["job"]["id"])
            record = {
                "sample_id": expected["id"],
                "attempt": 1,
                "parse_status": parsed.get("status"),
                "confidence": parsed["questions"][0].get("confidence"),
                "ai_parameters_match_expected": parameters_match(
                    parsed["questions"][0].get("parameters"), expected["parameters"]
                ),
                "job_id": job.get("id"),
                "job_status": job.get("status"),
                "teacher_parameters_applied": parameters_match(job.get("config"), expected["parameters"]),
                "output_url": job.get("output_url"),
                "output_opened_as_html": api.output_is_html(job.get("output_url")),
            }
            record["accepted"] = all(
                [
                    record["parse_status"] == "awaiting_confirmation",
                    record["job_status"] == "succeeded",
                    record["teacher_parameters_applied"],
                    record["output_opened_as_html"],
                ]
            )
            if index == 1:
                red_green = {
                    "red_status": "blocked",
                    "red_reason": red_reason,
                    "green_status": job.get("status"),
                    "green_output_url": job.get("output_url"),
                }
        except Exception as error:
            record = {"sample_id": expected["id"], "attempt": 1, "accepted": False, "reason": str(error)}
        records.append(record)
        print(f"[{index}/{len(MEDIA_EXPECTED)}] {expected['id']}: accepted={record['accepted']}", flush=True)
    return records, red_green


def run_uncertain(api: PublicApi) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for index in range(1, 4):
        path = MEDIA_DIR / f"uncertain-{index:02d}.png"
        try:
            parsed = api.json("/api/media/parse", upload_payload(path, "image/png"))["parse"]
            ready_count = sum(bool(item["ready_for_confirmation"]) for item in parsed["questions"])
            record = {
                "sample_id": path.stem,
                "status": parsed.get("status"),
                "ready_count": ready_count,
                "accepted": parsed.get("status") == "needs_input" and ready_count == 0,
                "reasons": [item.get("reason") for item in parsed["questions"]],
            }
        except Exception as error:
            record = {"sample_id": path.stem, "accepted": False, "reason": str(error)}
        records.append(record)
        print(f"[{index}/3] {path.stem}: accepted={record['accepted']}", flush=True)
    return records


def run_pdf(api: PublicApi) -> dict[str, Any]:
    path = MEDIA_DIR / "multi-question.pdf"
    try:
        parsed = api.json("/api/media/parse", upload_payload(path, "application/pdf"))["parse"]
        question = next(
            item for item in parsed["questions"] if item["parameters"].get("magnetic_field_t") == 0.5
        )
        expected = MEDIA_EXPECTED[0]
        payload = confirmation_payload({**parsed, "questions": [question]}, expected)
        submission = api.json("/api/media/confirm", payload)
        job = api.wait_job(submission["job"]["id"])
        record = {
            "page_count": parsed.get("page_count"),
            "question_count": len(parsed.get("questions", [])),
            "selected_question_id": question["id"],
            "job_status": job.get("status"),
            "output_url": job.get("output_url"),
            "output_opened_as_html": api.output_is_html(job.get("output_url")),
        }
        record["accepted"] = all(
            [record["page_count"] == 1, record["question_count"] == 2, record["job_status"] == "succeeded", record["output_opened_as_html"]]
        )
        return record
    except Exception as error:
        return {"accepted": False, "reason": str(error)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--origin", default=DEFAULT_ORIGIN)
    args = parser.parse_args()
    access_code = os.environ.get("COURSEWARE_ACCESS_CODE", "")
    if not access_code:
        print("缺少 COURSEWARE_ACCESS_CODE；请从钥匙串临时注入。", file=sys.stderr)
        return 2
    if RESULTS_PATH.exists():
        print(f"拒绝重跑：公网验收结果已存在 {RESULTS_PATH.relative_to(ROOT)}", file=sys.stderr)
        return 2

    api = PublicApi(args.base_url, args.origin, access_code)
    health = api.json("/api/health")
    task2_in = run_text_cases(api, load_fixture("task2-in-scope.json"), True)
    task2_out = run_text_cases(api, load_fixture("task2-out-of-scope.json"), False)
    benchmark = run_text_cases(api, load_fixture("benchmark-20.json"), True)
    media, red_green = run_media(api)
    uncertain = run_uncertain(api)
    pdf = run_pdf(api)

    benchmark_success = sum(bool(item["accepted"]) for item in benchmark)
    payload = {
        "acceptance": "aliyun-public-v2",
        "ran_at": datetime.now(timezone.utc).isoformat(),
        "base_url": api.base_url,
        "origin": api.origin,
        "health": health,
        "task2_in_scope": task2_in,
        "task2_out_of_scope": task2_out,
        "benchmark": {
            "successful": benchmark_success,
            "total": len(benchmark),
            "success_rate": benchmark_success / len(benchmark),
            "records": benchmark,
        },
        "media": media,
        "uncertain_media": uncertain,
        "pdf": pdf,
        "reverse_field_red_green": red_green,
    }
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    checks = {
        "task2_in_scope": sum(bool(item["accepted"]) for item in task2_in) == 5,
        "task2_out_of_scope": sum(bool(item["accepted"]) for item in task2_out) == 3,
        "benchmark": payload["benchmark"]["success_rate"] >= 0.60,
        "media": sum(bool(item["accepted"]) for item in media) == 5,
        "uncertain_media": sum(bool(item["accepted"]) for item in uncertain) == 3,
        "pdf": bool(pdf.get("accepted")),
        "red_green": red_green.get("red_status") == "blocked" and red_green.get("green_status") == "succeeded",
    }
    print(json.dumps(checks, ensure_ascii=False, indent=2))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
