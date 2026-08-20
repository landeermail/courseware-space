from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from services.feedback.service import LocalFeedbackStore  # noqa: E402
from services.feedback.review_workspace import (  # noqa: E402
    ReviewAccessError,
    ReviewClosedError,
    TeacherReviewWorkspace,
    apply_task_dispositions,
)


TEACHER_TOKEN = "a1" * 24
OTHER_TOKEN = "b2" * 24


def teacher_key(token: str) -> str:
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def task_key(token: str, task_id: str) -> str:
    return f"feedback/tasks/{teacher_key(token)}/{task_id}.json"


def seed_workspace(root: Path, token: str) -> None:
    tasks = [
        {
            "schema_version": 1,
            "task_id": "q01-v7-teacher-review",
            "courseware_id": "q01-vertical-circle",
            "revision_id": "q01-v7",
            "title": "第1题：竖直圆环双带电小球",
            "courseware_url": "q01-vertical-circle/",
            "assigned_at": "2026-07-30T10:00:00+08:00",
        },
        {
            "schema_version": 1,
            "task_id": "q01-v8-teacher-review",
            "courseware_id": "q01-vertical-circle",
            "revision_id": "q01-v8-1c89623d5bf0",
            "title": "第1题：竖直圆环双带电小球",
            "courseware_url": "q01-v8-1c89623d5bf0/",
            "assigned_at": "2026-08-12T10:00:00+08:00",
        },
    ]
    for task in tasks:
        path = root / task_key(token, task["task_id"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(task, ensure_ascii=False), encoding="utf-8")


def close_task(root: Path, token: str, task_id: str, courseware_id: str, revision_id: str) -> None:
    disposition = {
        "schema_version": 1,
        "record_type": "task_disposition",
        "disposition_id": "disposition-fixed-form-retired-20260820",
        "task_id": task_id,
        "courseware_id": courseware_id,
        "revision_id": revision_id,
        "status": "closed",
        "decided_at": "2026-08-20T00:00:00+08:00",
        "reason": "固定六维表单已退出默认评价协议，本任务结束，无需老师补填。",
        "decision_ref": "docs/adr/0011-default-to-minimal-courseware-research-experiments.md#决策",
    }
    path = (
        root
        / f"feedback/reviews/{teacher_key(token)}/{task_id}/{disposition['disposition_id']}.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(disposition, ensure_ascii=False), encoding="utf-8")


class TeacherReviewWorkspaceTests(unittest.TestCase):
    def test_single_teacher_can_use_stable_storage_key(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            seed_workspace(root, TEACHER_TOKEN)
            reviews = TeacherReviewWorkspace(
                LocalFeedbackStore(root), storage_key=teacher_key(TEACHER_TOKEN)
            )

            workspace = reviews.load("Z9" * 24)

            self.assertEqual(len(workspace["tasks"]), 2)

    def test_personal_token_loads_only_its_own_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            seed_workspace(root, TEACHER_TOKEN)
            reviews = TeacherReviewWorkspace(LocalFeedbackStore(root))

            workspace = reviews.load(TEACHER_TOKEN)

            self.assertEqual(workspace["tasks"][1]["revision_id"], "q01-v8-1c89623d5bf0")
            with self.assertRaises(ReviewAccessError):
                reviews.load(OTHER_TOKEN)

    def test_submission_completes_only_the_exact_revision_task(self) -> None:
        form = json.loads(
            (ROOT / "services" / "feedback" / "schema" / "example.json").read_text(
                encoding="utf-8"
            )
        )
        form = {"dimensions": form["dimensions"], "overall": form["overall"]}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            seed_workspace(root, TEACHER_TOKEN)
            reviews = TeacherReviewWorkspace(
                LocalFeedbackStore(root),
                clock=lambda: datetime(2026, 8, 13, 2, 0, tzinfo=timezone.utc),
                id_factory=lambda: "feedback-v8-first",
            )

            submitted = reviews.submit(TEACHER_TOKEN, "q01-v8-teacher-review", form)
            workspace = reviews.load(TEACHER_TOKEN)

            self.assertEqual(submitted["revision_id"], "q01-v8-1c89623d5bf0")
            self.assertEqual(submitted["courseware_id"], "q01-vertical-circle")
            tasks = {task["task_id"]: task for task in workspace["tasks"]}
            self.assertEqual(tasks["q01-v7-teacher-review"]["status"], "pending")
            self.assertEqual(tasks["q01-v8-teacher-review"]["status"], "reviewed")
            self.assertEqual(
                tasks["q01-v8-teacher-review"]["current_feedback"]["feedback_id"],
                "feedback-v8-first",
            )

    def test_edit_appends_a_new_version_and_preserves_history(self) -> None:
        example = json.loads(
            (ROOT / "services" / "feedback" / "schema" / "example.json").read_text(
                encoding="utf-8"
            )
        )
        first_form = {"dimensions": example["dimensions"], "overall": example["overall"]}
        second_form = json.loads(json.dumps(first_form))
        second_form["overall"]["note"] = "修改后的意见"
        ids = iter(("feedback-v8-first", "feedback-v8-second"))
        times = iter(
            (
                datetime(2026, 8, 13, 2, 0, tzinfo=timezone.utc),
                datetime(2026, 8, 13, 3, 0, tzinfo=timezone.utc),
            )
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            seed_workspace(root, TEACHER_TOKEN)
            reviews = TeacherReviewWorkspace(
                LocalFeedbackStore(root),
                clock=lambda: next(times),
                id_factory=lambda: next(ids),
            )

            first = reviews.submit(TEACHER_TOKEN, "q01-v8-teacher-review", first_form)
            second = reviews.submit(TEACHER_TOKEN, "q01-v8-teacher-review", second_form)
            task = next(
                task
                for task in reviews.load(TEACHER_TOKEN)["tasks"]
                if task["task_id"] == "q01-v8-teacher-review"
            )

            self.assertEqual(second["previous_feedback_id"], first["feedback_id"])
            self.assertEqual(
                [item["feedback_id"] for item in task["feedback_history"]],
                ["feedback-v8-first", "feedback-v8-second"],
            )
            self.assertEqual(task["current_feedback"]["overall"]["note"], "修改后的意见")
            self.assertEqual(
                len(list((root / "feedback/reviews").rglob("feedback-v8-*.json"))),
                2,
            )

    def test_disposition_closes_task_without_fabricating_feedback(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            seed_workspace(root, TEACHER_TOKEN)
            close_task(
                root,
                TEACHER_TOKEN,
                "q01-v8-teacher-review",
                "q01-vertical-circle",
                "q01-v8-1c89623d5bf0",
            )
            reviews = TeacherReviewWorkspace(LocalFeedbackStore(root))

            tasks = {task["task_id"]: task for task in reviews.load(TEACHER_TOKEN)["tasks"]}
            closed = tasks["q01-v8-teacher-review"]

            self.assertEqual(closed["status"], "closed")
            self.assertIsNone(closed["current_feedback"])
            self.assertEqual(closed["feedback_history"], [])
            self.assertEqual(closed["disposition"]["status"], "closed")

    def test_closed_task_rejects_new_structured_review(self) -> None:
        example = json.loads(
            (ROOT / "services" / "feedback" / "schema" / "example.json").read_text(
                encoding="utf-8"
            )
        )
        form = {"dimensions": example["dimensions"], "overall": example["overall"]}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            seed_workspace(root, TEACHER_TOKEN)
            close_task(
                root,
                TEACHER_TOKEN,
                "q01-v8-teacher-review",
                "q01-vertical-circle",
                "q01-v8-1c89623d5bf0",
            )
            reviews = TeacherReviewWorkspace(LocalFeedbackStore(root))

            with self.assertRaises(ReviewClosedError):
                reviews.submit(TEACHER_TOKEN, "q01-v8-teacher-review", form)

    def test_disposition_apply_is_idempotent_and_preserves_exact_bytes(self) -> None:
        item = {
            "schema_version": 1,
            "record_type": "task_disposition",
            "disposition_id": "disposition-fixed-form-retired-20260820",
            "task_id": "q01-v8-teacher-review",
            "courseware_id": "q01-vertical-circle",
            "revision_id": "q01-v8-1c89623d5bf0",
            "status": "closed",
            "decided_at": "2026-08-20T00:00:00+08:00",
            "reason": "固定六维表单已退出默认评价协议，本任务结束，无需老师补填。",
            "decision_ref": "docs/adr/0011-default-to-minimal-courseware-research-experiments.md#决策",
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            seed_workspace(root, TEACHER_TOKEN)
            store = LocalFeedbackStore(root)

            first = apply_task_dispositions(store, teacher_key(TEACHER_TOKEN), [item])
            second = apply_task_dispositions(store, teacher_key(TEACHER_TOKEN), [item])

            self.assertEqual(first, {"written": 1, "existing": 0})
            self.assertEqual(second, {"written": 0, "existing": 1})

    def test_courseware_entry_resolves_to_latest_assigned_exact_task(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            seed_workspace(root, TEACHER_TOKEN)
            reviews = TeacherReviewWorkspace(LocalFeedbackStore(root))

            workspace = reviews.load(TEACHER_TOKEN, courseware_id="q01-vertical-circle")

            self.assertEqual(len(workspace["tasks"]), 1)
            self.assertEqual(workspace["tasks"][0]["task_id"], "q01-v8-teacher-review")
            self.assertEqual(workspace["tasks"][0]["revision_id"], "q01-v8-1c89623d5bf0")


if __name__ == "__main__":
    unittest.main()
