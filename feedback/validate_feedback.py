#!/usr/bin/env python3
"""Validate six-dimension courseware feedback without third-party packages."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import sys
from typing import Any


DIMENSIONS = (
    "causal_presentation",
    "process_visibility",
    "effective_interaction",
    "task_driven",
    "verifiability",
    "exam_connection",
)
REJECTION_REASONS = frozenset(
    (*DIMENSIONS, "usability", "information_overload", "other")
)
TOP_LEVEL_KEYS = frozenset(
    {
        "schema_version",
        "feedback_id",
        "session_id",
        "courseware_id",
        "reviewer_role",
        "reviewed_at",
        "dimensions",
        "overall",
    }
)
FEEDBACK_ID = re.compile(r"^[a-z0-9][a-z0-9-]{7,79}$")
SESSION_ID = re.compile(r"^[a-z0-9][a-z0-9-]{3,79}$")
COURSEWARE_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _exact_keys(value: object, expected: frozenset[str], label: str) -> list[str]:
    if not isinstance(value, dict):
        return [f"{label} 必须是对象"]
    actual = frozenset(value)
    errors = [f"{label} 缺少字段：{key}" for key in sorted(expected - actual)]
    errors.extend(f"{label} 不允许字段：{key}" for key in sorted(actual - expected))
    return errors


def _text(value: object, label: str, *, maximum: int = 2000) -> list[str]:
    if not isinstance(value, str):
        return [f"{label} 必须是字符串"]
    if len(value) > maximum:
        return [f"{label} 不能超过 {maximum} 个字符"]
    return []


def _date_time(value: object) -> bool:
    if not isinstance(value, str) or not value:
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return "T" in value and parsed.tzinfo is not None


def validate_feedback(payload: Any) -> list[str]:
    """Return all contract errors; an empty list means valid feedback."""

    errors = _exact_keys(payload, TOP_LEVEL_KEYS, "反馈")
    if not isinstance(payload, dict):
        return errors

    if payload.get("schema_version") != 1:
        errors.append("schema_version 必须为 1")

    identifiers = (
        ("feedback_id", FEEDBACK_ID, 8, 80),
        ("session_id", SESSION_ID, 4, 80),
        ("courseware_id", COURSEWARE_ID, 3, 100),
    )
    for key, pattern, minimum, maximum in identifiers:
        value = payload.get(key)
        if not isinstance(value, str) or not minimum <= len(value) <= maximum or not pattern.fullmatch(value):
            errors.append(f"{key} 格式无效")

    if payload.get("reviewer_role") not in {"leader", "teacher"}:
        errors.append("reviewer_role 必须为 leader 或 teacher")
    if not _date_time(payload.get("reviewed_at")):
        errors.append("reviewed_at 必须为 ISO 8601 date-time")

    dimensions = payload.get("dimensions")
    errors.extend(_exact_keys(dimensions, frozenset(DIMENSIONS), "dimensions"))
    if isinstance(dimensions, dict):
        for key in DIMENSIONS:
            value = dimensions.get(key)
            label = f"dimensions.{key}"
            errors.extend(_exact_keys(value, frozenset({"verdict", "note"}), label))
            if not isinstance(value, dict):
                continue
            verdict = value.get("verdict")
            note = value.get("note")
            if verdict not in {"pass", "fail"}:
                errors.append(f"{label}.verdict 必须为 pass 或 fail")
            errors.extend(_text(note, f"{label}.note"))
            if verdict == "fail" and isinstance(note, str) and not note.strip():
                errors.append(f"{label}.note 在 fail 时不能为空")

    overall = payload.get("overall")
    errors.extend(
        _exact_keys(overall, frozenset({"verdict", "rejection_reasons", "note"}), "overall")
    )
    if isinstance(overall, dict):
        verdict = overall.get("verdict")
        reasons = overall.get("rejection_reasons")
        note = overall.get("note")
        if verdict not in {"satisfied", "reject"}:
            errors.append("overall.verdict 必须为 satisfied 或 reject")
        if not isinstance(reasons, list):
            errors.append("overall.rejection_reasons 必须是数组")
            reasons = []
        else:
            invalid = [reason for reason in reasons if reason not in REJECTION_REASONS]
            if invalid:
                errors.append(f"overall.rejection_reasons 包含无效值：{invalid[0]}")
            if len(reasons) != len(set(reasons)):
                errors.append("overall.rejection_reasons 不能重复")
        errors.extend(_text(note, "overall.note"))
        if verdict == "satisfied" and reasons:
            errors.append("overall 为 satisfied 时不能包含打回原因")
        if verdict == "reject" and not reasons:
            errors.append("overall 为 reject 时至少选择一个打回原因")
        if "other" in reasons and isinstance(note, str) and not note.strip():
            errors.append("选择 other 时 overall.note 不能为空")

    return errors


def validate_file(path: Path) -> list[str]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        return [f"无法读取 JSON：{error}"]
    return validate_feedback(payload)


def main() -> int:
    parser = argparse.ArgumentParser(description="校验课件六维反馈 JSON")
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args()

    failed = False
    for path in args.paths:
        errors = validate_file(path)
        if errors:
            failed = True
            print(f"无效反馈：{path}", file=sys.stderr)
            for error in errors:
                print(f"- {error}", file=sys.stderr)
        else:
            print(f"有效反馈：{path}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
