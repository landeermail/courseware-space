#!/usr/bin/env python3
"""Build the append-only q474 free-feedback task and relayed teacher response."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys


STORAGE_KEY_PATTERN = re.compile(r"^[0-9a-f]{64}$")
TASK_ID = "q474-v1-teacher-feedback"
FEEDBACK_ID = "feedback-q474-teacher-relay-20260820"


def canonical_json(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode(
        "utf-8"
    )


def write_new(root: Path, key: str, value: object) -> None:
    target = root / key
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with target.open("xb") as stream:
            stream.write(canonical_json(value))
    except FileExistsError as error:
        raise RuntimeError(f"对象已存在：{key}") from error


def main() -> int:
    parser = argparse.ArgumentParser(description="生成 q474 自由反馈任务与老师转述反馈对象")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    teacher_key = os.environ.get("COURSEWARE_TEACHER_STORAGE_KEY", "")
    if not STORAGE_KEY_PATTERN.fullmatch(teacher_key):
        print("COURSEWARE_TEACHER_STORAGE_KEY 必须是现有老师目录的 64 位 SHA-256", file=sys.stderr)
        return 2
    if args.output.exists():
        print("输出目录已存在；为避免覆盖，已停止。", file=sys.stderr)
        return 2

    task = {
        "schema_version": 1,
        "task_id": TASK_ID,
        "courseware_id": "q474-longitudinal-wave",
        "revision_id": "q474-v1-39e8e4f62f4b",
        "title": "第474题：纵波弹簧标记点",
        "courseware_url": "q474-v1-39e8e4f62f4b/",
        "assigned_at": "2026-08-20T13:57:33+08:00",
        "feedback_mode": "freeform",
        "prompt": "请说说这份课件最值得保留的地方，或学生仍可能卡在哪里。",
    }
    response = {
        "schema_version": 3,
        "record_type": "free_feedback",
        "feedback_id": FEEDBACK_ID,
        "task_id": TASK_ID,
        "courseware_id": task["courseware_id"],
        "revision_id": task["revision_id"],
        "reviewed_at": "2026-08-20T14:52:29+08:00",
        "previous_feedback_id": None,
        "source_channel": "product_owner_relay",
        "source_ref": "research/experiments/474-longitudinal-wave.md#顾问老师原意经用户转述",
        "message": "老师也表示很满意。",
    }

    try:
        write_new(
            args.output,
            f"feedback/tasks/{teacher_key}/{TASK_ID}.json",
            task,
        )
        write_new(
            args.output,
            f"feedback/reviews/{teacher_key}/{TASK_ID}/{FEEDBACK_ID}.json",
            response,
        )
        write_new(
            args.output,
            "review-updates.json",
            [{"task": task, "feedback": response}],
        )
    except (OSError, RuntimeError) as error:
        print(f"无法生成 q474 反馈更新：{error}", file=sys.stderr)
        return 1

    print("q474_feedback_update_created tasks=1 relayed_feedback=1 deployment_payload=1 cloud_changes=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
