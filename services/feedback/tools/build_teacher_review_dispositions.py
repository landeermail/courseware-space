#!/usr/bin/env python3
"""Build append-only dispositions for retired fixed-form review tasks."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
from typing import Any


STORAGE_KEY_PATTERN = re.compile(r"^[0-9a-f]{64}$")
DISPOSITION_ID = "disposition-fixed-form-retired-20260820"
DECIDED_AT = "2026-08-20T00:00:00+08:00"
DECISION_REF = "docs/adr/0011-default-to-minimal-courseware-research-experiments.md#决策"
REASON = "固定六维表单已退出默认评价协议，本任务结束，无需老师补填。"

TASKS: tuple[dict[str, str], ...] = (
    {
        "task_id": "q01-v8-teacher-review",
        "courseware_id": "q01-vertical-circle",
        "revision_id": "q01-v8-1c89623d5bf0",
    },
    {
        "task_id": "q07-v4-teacher-review",
        "courseware_id": "q07-glass-rod-tir",
        "revision_id": "5c8590bd2060",
    },
)


def canonical_json(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode(
        "utf-8"
    )


def disposition(task: dict[str, str]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "record_type": "task_disposition",
        "disposition_id": DISPOSITION_ID,
        "task_id": task["task_id"],
        "courseware_id": task["courseware_id"],
        "revision_id": task["revision_id"],
        "status": "closed",
        "decided_at": DECIDED_AT,
        "reason": REASON,
        "decision_ref": DECISION_REF,
    }


def write_new(root: Path, key: str, value: object) -> None:
    target = root / key
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with target.open("xb") as stream:
            stream.write(canonical_json(value))
    except FileExistsError as error:
        raise RuntimeError(f"处置对象已存在：{key}") from error


def main() -> int:
    parser = argparse.ArgumentParser(description="生成 q01、q07 旧固定表单任务的追加式结束记录")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    teacher_key = os.environ.get("COURSEWARE_TEACHER_STORAGE_KEY", "")
    if not STORAGE_KEY_PATTERN.fullmatch(teacher_key):
        print("COURSEWARE_TEACHER_STORAGE_KEY 必须是现有老师目录的 64 位 SHA-256", file=sys.stderr)
        return 2
    if args.output.exists():
        print("输出目录已存在；为避免覆盖，已停止。", file=sys.stderr)
        return 2

    try:
        for task in TASKS:
            value = disposition(task)
            write_new(
                args.output,
                f"feedback/reviews/{teacher_key}/{task['task_id']}/{DISPOSITION_ID}.json",
                value,
            )
    except (OSError, RuntimeError) as error:
        print(f"无法生成处置记录：{error}", file=sys.stderr)
        return 1

    print("dispositions_created tasks=2 cloud_changes=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
