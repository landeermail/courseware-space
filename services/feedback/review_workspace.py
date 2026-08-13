"""Teacher-scoped review tasks and immutable feedback history."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any, Callable
import uuid

from services.feedback.access_control import validate_access_code
from services.feedback.service import (
    FeedbackStore,
    FeedbackStoreError,
    FeedbackValidationError,
    validate_feedback,
)


class ReviewAccessError(PermissionError):
    pass


class ReviewDataError(RuntimeError):
    pass


TASK_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class TeacherReviewWorkspace:
    """Hide teacher identity, task lookup and history behind one interface."""

    def __init__(
        self,
        store: FeedbackStore,
        *,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
        storage_key: str | None = None,
    ) -> None:
        self.store = store
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.id_factory = id_factory or (lambda: f"feedback-{uuid.uuid4()}")
        self.storage_key = storage_key

    def load(
        self,
        personal_token: str,
        *,
        courseware_id: str | None = None,
    ) -> dict[str, Any]:
        teacher_key = self._teacher_key(personal_token)
        tasks = self._load_tasks(teacher_key)
        if courseware_id is not None:
            matching = [task for task in tasks if task.get("courseware_id") == courseware_id]
            tasks = matching[-1:] if matching else []
        for task in tasks:
            task_id = self._task_id(task)
            history = self._history(teacher_key, task_id)
            task["status"] = "reviewed" if history else "pending"
            task["current_feedback"] = history[-1] if history else None
            task["feedback_history"] = history
        return {"schema_version": 1, "tasks": tasks}

    def submit(
        self,
        personal_token: str,
        task_id: str,
        form: dict[str, Any],
    ) -> dict[str, Any]:
        teacher_key = self._teacher_key(personal_token)
        tasks = self._load_tasks(teacher_key)
        task = next(
            (candidate for candidate in tasks if candidate.get("task_id") == task_id),
            None,
        )
        if task is None:
            raise ReviewAccessError("评价任务不存在")
        task_id = self._task_id(task)
        reviewed_at = self.clock().astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        feedback_id = self.id_factory()
        validation_payload = {
            "schema_version": 1,
            "feedback_id": feedback_id,
            "session_id": task_id,
            "courseware_id": task.get("courseware_id"),
            "reviewer_role": "teacher",
            "reviewed_at": reviewed_at,
            "dimensions": form.get("dimensions"),
            "overall": form.get("overall"),
        }
        errors = validate_feedback(validation_payload)
        if errors:
            raise FeedbackValidationError("；".join(errors))
        revision_id = task.get("revision_id")
        if not isinstance(revision_id, str) or not revision_id:
            raise ReviewDataError("评价任务缺少精确 revision")
        previous = self._history(teacher_key, task_id)
        payload = {
            "schema_version": 2,
            "feedback_id": feedback_id,
            "task_id": task_id,
            "courseware_id": task["courseware_id"],
            "revision_id": revision_id,
            "reviewed_at": reviewed_at,
            "previous_feedback_id": previous[-1]["feedback_id"] if previous else None,
            "dimensions": form["dimensions"],
            "overall": form["overall"],
        }
        key = f"feedback/reviews/{teacher_key}/{task_id}/{feedback_id}.json"
        body = (json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode(
            "utf-8"
        )
        self.store.write(key, body)
        return payload

    def _load_tasks(self, teacher_key: str) -> list[dict[str, Any]]:
        prefix = f"feedback/tasks/{teacher_key}/"
        keys = self.store.list(prefix)
        if not keys:
            raise ReviewAccessError("个人链接无效")
        tasks: list[dict[str, Any]] = []
        for key in keys:
            try:
                task = json.loads(self.store.read(key))
            except (FeedbackStoreError, UnicodeDecodeError, json.JSONDecodeError) as error:
                raise ReviewDataError("老师评价任务数据无效") from error
            if not isinstance(task, dict) or task.get("schema_version") != 1:
                raise ReviewDataError("老师评价任务数据无效")
            self._task_id(task)
            tasks.append(task)
        tasks.sort(key=lambda task: (str(task.get("assigned_at", "")), task["task_id"]))
        return tasks

    def _history(self, teacher_key: str, task_id: str) -> list[dict[str, Any]]:
        prefix = f"feedback/reviews/{teacher_key}/{task_id}/"
        history: list[dict[str, Any]] = []
        for key in self.store.list(prefix):
            try:
                item = json.loads(self.store.read(key))
            except (FeedbackStoreError, UnicodeDecodeError, json.JSONDecodeError) as error:
                raise ReviewDataError("老师评价历史数据无效") from error
            if not isinstance(item, dict) or item.get("schema_version") != 2:
                raise ReviewDataError("老师评价历史数据无效")
            history.append(item)
        history.sort(key=lambda item: (str(item.get("reviewed_at", "")), str(item.get("feedback_id", ""))))
        return history

    @staticmethod
    def _task_id(task: object) -> str:
        if not isinstance(task, dict):
            raise ReviewDataError("老师评价任务数据无效")
        task_id = task.get("task_id")
        if not isinstance(task_id, str) or not TASK_ID.fullmatch(task_id):
            raise ReviewDataError("老师评价任务数据无效")
        return task_id

    def _teacher_key(self, personal_token: str) -> str:
        try:
            validate_access_code(personal_token)
        except RuntimeError as error:
            raise ReviewAccessError("个人链接无效") from error
        if not personal_token:
            raise ReviewAccessError("个人链接无效")
        return self.storage_key or hashlib.sha256(personal_token.encode("ascii")).hexdigest()
