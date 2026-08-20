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


class ReviewClosedError(ReviewAccessError):
    pass


class ReviewDataError(RuntimeError):
    pass


TASK_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
STORAGE_KEY = re.compile(r"^[0-9a-f]{64}$")


def canonical_json(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode(
        "utf-8"
    )


def apply_task_dispositions(
    store: FeedbackStore,
    storage_key: str,
    dispositions: list[dict[str, Any]],
) -> dict[str, int]:
    """Append exact task dispositions or verify an identical prior append."""

    if not STORAGE_KEY.fullmatch(storage_key) or not 1 <= len(dispositions) <= 10:
        raise ReviewDataError("老师评价任务处置配置无效")
    workspace = TeacherReviewWorkspace(store, storage_key=storage_key)
    tasks = {workspace._task_id(task): task for task in workspace._load_tasks(storage_key)}
    written = 0
    existing = 0
    for item in dispositions:
        if not isinstance(item, dict):
            raise ReviewDataError("老师评价任务处置配置无效")
        task_id = item.get("task_id")
        task = tasks.get(task_id) if isinstance(task_id, str) else None
        if task is None:
            raise ReviewDataError("老师评价任务处置未匹配现有任务")
        workspace._validate_disposition(item, task)
        key = f"feedback/reviews/{storage_key}/{task_id}/{item['disposition_id']}.json"
        body = canonical_json(item)
        try:
            store.write(key, body)
            written += 1
        except FeedbackStoreError:
            try:
                prior = store.read(key)
            except FeedbackStoreError as error:
                raise ReviewDataError("老师评价任务处置写入失败") from error
            if prior != body:
                raise ReviewDataError("老师评价任务处置对象已存在但内容不同")
            existing += 1
    return {"written": written, "existing": existing}


def apply_teacher_feedback_updates(
    store: FeedbackStore,
    storage_key: str,
    updates: list[dict[str, Any]],
) -> dict[str, int]:
    """Append exact free-feedback tasks and records or verify identical prior bytes."""

    if not STORAGE_KEY.fullmatch(storage_key) or not 1 <= len(updates) <= 10:
        raise ReviewDataError("老师反馈更新配置无效")
    workspace = TeacherReviewWorkspace(store, storage_key=storage_key)
    written = 0
    existing = 0
    for update in updates:
        if not isinstance(update, dict) or set(update) != {"task", "feedback"}:
            raise ReviewDataError("老师反馈更新配置无效")
        task = update.get("task")
        feedback = update.get("feedback")
        workspace._validate_task(task, require_freeform=True)
        if not isinstance(task, dict) or not isinstance(feedback, dict):
            raise ReviewDataError("老师反馈更新配置无效")
        workspace._validate_record_identity(feedback, task)
        workspace._validate_free_feedback(feedback, task)
        task_id = workspace._task_id(task)
        feedback_id = feedback["feedback_id"]
        for key, value in (
            (f"feedback/tasks/{storage_key}/{task_id}.json", task),
            (f"feedback/reviews/{storage_key}/{task_id}/{feedback_id}.json", feedback),
        ):
            body = canonical_json(value)
            try:
                store.write(key, body)
                written += 1
            except FeedbackStoreError:
                try:
                    prior = store.read(key)
                except FeedbackStoreError as error:
                    raise ReviewDataError("老师反馈更新写入失败") from error
                if prior != body:
                    raise ReviewDataError("老师反馈更新对象已存在但内容不同")
                existing += 1
    return {"written": written, "existing": existing}


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
            history, disposition = self._review_records(teacher_key, task)
            task["status"] = "reviewed" if history else "closed" if disposition else "pending"
            task["current_feedback"] = history[-1] if history else None
            task["feedback_history"] = history
            task["disposition"] = disposition
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
        previous, disposition = self._review_records(teacher_key, task)
        if disposition and not previous:
            raise ReviewClosedError("评价任务已结束，无需补填")
        reviewed_at = self.clock().astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        feedback_id = self.id_factory()
        revision_id = task.get("revision_id")
        if not isinstance(revision_id, str) or not revision_id:
            raise ReviewDataError("评价任务缺少精确 revision")
        if task.get("feedback_mode", "structured") == "freeform":
            return self._submit_freeform(
                teacher_key,
                task,
                task_id,
                form,
                previous,
                feedback_id,
                reviewed_at,
            )
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
        body = canonical_json(payload)
        self.store.write(key, body)
        return payload

    def _submit_freeform(
        self,
        teacher_key: str,
        task: dict[str, Any],
        task_id: str,
        form: dict[str, Any],
        previous: list[dict[str, Any]],
        feedback_id: str,
        reviewed_at: str,
    ) -> dict[str, Any]:
        if not isinstance(form, dict) or set(form) != {"message"}:
            raise FeedbackValidationError("自由反馈只允许 message 字段")
        message = form.get("message")
        if not isinstance(message, str) or not message.strip():
            raise FeedbackValidationError("请写下最想告诉我们的内容")
        message = message.strip()
        if len(message) > 4000:
            raise FeedbackValidationError("反馈不能超过 4000 个字符")
        payload = {
            "schema_version": 3,
            "record_type": "free_feedback",
            "feedback_id": feedback_id,
            "task_id": task_id,
            "courseware_id": task["courseware_id"],
            "revision_id": task["revision_id"],
            "reviewed_at": reviewed_at,
            "previous_feedback_id": previous[-1]["feedback_id"] if previous else None,
            "source_channel": "teacher_entry",
            "message": message,
        }
        key = f"feedback/reviews/{teacher_key}/{task_id}/{feedback_id}.json"
        self.store.write(key, canonical_json(payload))
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
            self._validate_task(task)
            tasks.append(task)
        tasks.sort(key=lambda task: (str(task.get("assigned_at", "")), task["task_id"]))
        return tasks

    def _review_records(
        self,
        teacher_key: str,
        task: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
        task_id = self._task_id(task)
        prefix = f"feedback/reviews/{teacher_key}/{task_id}/"
        history: list[dict[str, Any]] = []
        dispositions: list[dict[str, Any]] = []
        for key in self.store.list(prefix):
            try:
                item = json.loads(self.store.read(key))
            except (FeedbackStoreError, UnicodeDecodeError, json.JSONDecodeError) as error:
                raise ReviewDataError("老师评价历史数据无效") from error
            if not isinstance(item, dict):
                raise ReviewDataError("老师评价历史数据无效")
            if item.get("schema_version") == 2 and item.get("record_type", "feedback") == "feedback":
                self._validate_record_identity(item, task)
                history.append(item)
                continue
            if item.get("schema_version") == 3 and item.get("record_type") == "free_feedback":
                self._validate_record_identity(item, task)
                self._validate_free_feedback(item, task)
                history.append(item)
                continue
            if item.get("schema_version") == 1 and item.get("record_type") == "task_disposition":
                self._validate_disposition(item, task)
                dispositions.append(item)
                continue
            raise ReviewDataError("老师评价历史数据无效")
        history.sort(key=lambda item: (str(item.get("reviewed_at", "")), str(item.get("feedback_id", ""))))
        dispositions.sort(
            key=lambda item: (str(item.get("decided_at", "")), str(item.get("disposition_id", "")))
        )
        return history, dispositions[-1] if dispositions else None

    @staticmethod
    def _validate_free_feedback(item: dict[str, Any], task: dict[str, Any]) -> None:
        if task.get("feedback_mode", "structured") != "freeform":
            raise ReviewDataError("老师自由反馈与任务类型不一致")
        message = item.get("message")
        if not isinstance(message, str) or not message.strip() or len(message) > 4000:
            raise ReviewDataError("老师自由反馈数据无效")
        source_channel = item.get("source_channel")
        if source_channel not in {"teacher_entry", "product_owner_relay"}:
            raise ReviewDataError("老师自由反馈数据无效")
        source_ref = item.get("source_ref")
        if source_channel == "product_owner_relay" and (
            not isinstance(source_ref, str) or not source_ref.strip()
        ):
            raise ReviewDataError("转述反馈缺少来源")
        feedback_id = item.get("feedback_id")
        reviewed_at = item.get("reviewed_at")
        if not isinstance(feedback_id, str) or not TASK_ID.fullmatch(feedback_id):
            raise ReviewDataError("老师自由反馈数据无效")
        if not isinstance(reviewed_at, str) or not reviewed_at.strip():
            raise ReviewDataError("老师自由反馈数据无效")

    def _validate_task(self, task: object, *, require_freeform: bool = False) -> None:
        if not isinstance(task, dict) or task.get("schema_version") != 1:
            raise ReviewDataError("老师评价任务数据无效")
        self._task_id(task)
        feedback_mode = task.get("feedback_mode", "structured")
        if feedback_mode not in {"structured", "freeform"}:
            raise ReviewDataError("老师评价任务数据无效")
        if require_freeform and feedback_mode != "freeform":
            raise ReviewDataError("老师反馈更新只允许自由反馈任务")
        for field in ("courseware_id", "revision_id", "title", "courseware_url", "assigned_at"):
            if not isinstance(task.get(field), str) or not task[field].strip():
                raise ReviewDataError("老师评价任务数据无效")
        prompt = task.get("prompt")
        if prompt is not None and (
            not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 600
        ):
            raise ReviewDataError("老师评价任务数据无效")

    @staticmethod
    def _validate_record_identity(item: dict[str, Any], task: dict[str, Any]) -> None:
        for field in ("task_id", "courseware_id", "revision_id"):
            if item.get(field) != task.get(field):
                raise ReviewDataError("老师评价历史与任务身份不一致")

    def _validate_disposition(self, item: dict[str, Any], task: dict[str, Any]) -> None:
        self._validate_record_identity(item, task)
        disposition_id = item.get("disposition_id")
        if not isinstance(disposition_id, str) or not TASK_ID.fullmatch(disposition_id):
            raise ReviewDataError("老师评价任务处置数据无效")
        if item.get("status") != "closed":
            raise ReviewDataError("老师评价任务处置数据无效")
        for field in ("decided_at", "reason", "decision_ref"):
            if not isinstance(item.get(field), str) or not item[field].strip():
                raise ReviewDataError("老师评价任务处置数据无效")

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
