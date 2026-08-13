#!/usr/bin/env python3
"""Build the first teacher review task/history objects without cloud writes."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
TOKEN_PATTERN = re.compile(r"^[0-9a-f]{48}$")
SOURCE_REVIEW = ROOT / "services" / "feedback" / "history" / "review-q01-20260730.json"


TASKS: tuple[dict[str, Any], ...] = (
    {
        "schema_version": 1,
        "task_id": "q01-v7-teacher-review",
        "courseware_id": "q01-vertical-circle",
        "revision_id": "q01-v7",
        "title": "第1题：竖直圆环双带电小球",
        "courseware_url": "q01-vertical-circle/",
        "assigned_at": "2026-07-30T16:00:01.442Z",
    },
    {
        "schema_version": 1,
        "task_id": "q01-v8-teacher-review",
        "courseware_id": "q01-vertical-circle",
        "revision_id": "q01-v8-1c89623d5bf0",
        "title": "第1题：竖直圆环双带电小球",
        "courseware_url": "q01-v8-1c89623d5bf0/",
        "assigned_at": "2026-08-05T09:48:00Z",
    },
    {
        "schema_version": 1,
        "task_id": "q07-v4-teacher-review",
        "courseware_id": "q07-glass-rod-tir",
        "revision_id": "5c8590bd2060",
        "title": "第7题：玻璃管全反射计数",
        "courseware_url": "q07-v4-5bb63ec7f581/",
        "assigned_at": "2026-08-12T00:00:00Z",
    },
)


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
        raise RuntimeError(f"seed 对象已存在：{key}") from error


def migrated_q01_v7() -> dict[str, Any]:
    source = json.loads(SOURCE_REVIEW.read_text(encoding="utf-8"))
    return {
        "schema_version": 2,
        "feedback_id": source["feedback_id"],
        "task_id": "q01-v7-teacher-review",
        "courseware_id": source["courseware_id"],
        "revision_id": "q01-v7",
        "reviewed_at": source["reviewed_at"],
        "previous_feedback_id": None,
        "dimensions": source["dimensions"],
        "overall": source["overall"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="生成首位老师评价任务与 q01 v7 历史迁移对象")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    token = os.environ.get("COURSEWARE_TEACHER_TOKEN", "")
    if not TOKEN_PATTERN.fullmatch(token):
        print("COURSEWARE_TEACHER_TOKEN 必须是 48 位小写十六进制值", file=sys.stderr)
        return 2
    if args.output.exists():
        print("输出目录已存在；为避免覆盖，已停止。", file=sys.stderr)
        return 2

    teacher_key = hashlib.sha256(token.encode("ascii")).hexdigest()
    try:
        for task in TASKS:
            write_new(
                args.output,
                f"feedback/tasks/{teacher_key}/{task['task_id']}.json",
                task,
            )
        review = migrated_q01_v7()
        write_new(
            args.output,
            f"feedback/reviews/{teacher_key}/q01-v7-teacher-review/{review['feedback_id']}.json",
            review,
        )
    except (OSError, KeyError, json.JSONDecodeError, RuntimeError) as error:
        print(f"无法生成 seed：{error}", file=sys.stderr)
        return 1

    print("seed_created tasks=3 migrated_reviews=1 cloud_changes=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
