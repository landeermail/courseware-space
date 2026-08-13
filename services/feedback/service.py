"""Validate anonymous courseware feedback and append it to private storage."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from typing import Any, Protocol


PRIVATE_BUCKET = re.compile(r"^courseware-space-private-[a-z0-9-]+$")

from services.feedback.schema.validate_feedback import validate_feedback


class FeedbackValidationError(ValueError):
    pass


class FeedbackStoreError(RuntimeError):
    pass


class FeedbackStore(Protocol):
    backend: str

    def write(self, key: str, body: bytes) -> None:
        ...

    def read(self, key: str) -> bytes:
        ...

    def list(self, prefix: str) -> list[str]:
        ...


class LocalFeedbackStore:
    backend = "local"

    def __init__(self, root: Path) -> None:
        self.root = root

    def write(self, key: str, body: bytes) -> None:
        target = self._target(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            with target.open("xb") as stream:
                stream.write(body)
        except FileExistsError as error:
            raise FeedbackStoreError("反馈编号已存在") from error

    def read(self, key: str) -> bytes:
        target = self._target(key)
        try:
            return target.read_bytes()
        except FileNotFoundError as error:
            raise FeedbackStoreError("反馈对象不存在") from error
        except OSError as error:
            raise FeedbackStoreError("反馈对象读取失败") from error

    def list(self, prefix: str) -> list[str]:
        base = self._target(prefix)
        if not base.exists():
            return []
        if base.is_file():
            return [prefix]
        try:
            return sorted(
                path.relative_to(self.root.resolve()).as_posix()
                for path in base.rglob("*")
                if path.is_file()
            )
        except OSError as error:
            raise FeedbackStoreError("反馈对象列举失败") from error

    def _target(self, key: str) -> Path:
        if not key.startswith("feedback/"):
            raise FeedbackStoreError("反馈存储路径无效")
        target = (self.root / key).resolve()
        root = self.root.resolve()
        try:
            target.relative_to(root)
        except ValueError as error:
            raise FeedbackStoreError("反馈存储路径无效") from error
        return target


class OssFeedbackStore:
    backend = "oss"

    def __init__(self, bucket: str, region: str, endpoint: str | None = None) -> None:
        if not PRIVATE_BUCKET.fullmatch(bucket):
            raise FeedbackStoreError("反馈必须写入 courseware-space-private-* bucket")
        if not re.fullmatch(r"cn-[a-z0-9-]+", region):
            raise FeedbackStoreError("COURSEWARE_OSS_REGION 格式无效")
        try:
            import alibabacloud_oss_v2 as oss
        except ImportError as error:
            raise FeedbackStoreError("云端反馈存储缺少 alibabacloud-oss-v2") from error
        self.oss = oss
        self.bucket = bucket
        provider = oss.credentials.EnvironmentVariableCredentialsProvider()
        config = oss.config.load_default()
        config.credentials_provider = provider
        config.region = region
        config.endpoint = endpoint or f"https://oss-{region}-internal.aliyuncs.com"
        self.client = oss.Client(config)

    def write(self, key: str, body: bytes) -> None:
        self._feedback_key(key)
        try:
            result = self.client.put_object(
                self.oss.PutObjectRequest(
                    bucket=self.bucket,
                    key=key,
                    body=body,
                    content_type="application/json; charset=utf-8",
                    cache_control="no-store",
                    forbid_overwrite=True,
                )
            )
        except Exception as error:
            raise FeedbackStoreError(f"反馈写入 OSS 失败：{type(error).__name__}") from error
        if not 200 <= result.status_code < 300:
            raise FeedbackStoreError(f"反馈写入 OSS 失败（HTTP {result.status_code}）")

    def read(self, key: str) -> bytes:
        self._feedback_key(key)
        try:
            result = self.client.get_object(
                self.oss.GetObjectRequest(bucket=self.bucket, key=key)
            )
            status = getattr(result, "status_code", 200)
            if not 200 <= status < 300:
                raise FeedbackStoreError(f"反馈读取 OSS 失败（HTTP {status}）")
            body = result.body
            if hasattr(body, "read"):
                body = body.read()
            if isinstance(body, str):
                body = body.encode("utf-8")
            if not isinstance(body, bytes):
                raise FeedbackStoreError("反馈读取 OSS 返回无效内容")
            return body
        except FeedbackStoreError:
            raise
        except Exception as error:
            raise FeedbackStoreError(f"反馈读取 OSS 失败：{type(error).__name__}") from error

    def list(self, prefix: str) -> list[str]:
        self._feedback_key(prefix)
        keys: list[str] = []
        continuation: str | None = None
        try:
            while True:
                result = self.client.list_objects_v2(
                    self.oss.ListObjectsV2Request(
                        bucket=self.bucket,
                        prefix=prefix,
                        continuation_token=continuation,
                    )
                )
                status = getattr(result, "status_code", 200)
                if not 200 <= status < 300:
                    raise FeedbackStoreError(f"反馈列举 OSS 失败（HTTP {status}）")
                for item in getattr(result, "contents", None) or []:
                    key = getattr(item, "key", "")
                    if not isinstance(key, str) or not key.startswith(prefix):
                        raise FeedbackStoreError("反馈列举 OSS 返回越界对象")
                    keys.append(key)
                if not getattr(result, "is_truncated", False):
                    break
                continuation = getattr(result, "next_continuation_token", None)
                if not continuation:
                    raise FeedbackStoreError("反馈列举 OSS 缺少分页游标")
        except FeedbackStoreError:
            raise
        except Exception as error:
            raise FeedbackStoreError(f"反馈列举 OSS 失败：{type(error).__name__}") from error
        return sorted(keys)

    @staticmethod
    def _feedback_key(key: str) -> str:
        if not isinstance(key, str) or not key.startswith("feedback/") or ".." in key.split("/"):
            raise FeedbackStoreError("反馈 OSS 前缀无效")
        return key


class FeedbackService:
    def __init__(self, store: FeedbackStore) -> None:
        self.store = store

    def submit(self, payload: Any) -> str:
        errors = validate_feedback(payload)
        if errors:
            raise FeedbackValidationError("；".join(errors))
        reviewed_at = datetime.fromisoformat(payload["reviewed_at"].replace("Z", "+00:00"))
        reviewed_at = reviewed_at.astimezone(timezone.utc)
        key = (
            f"feedback/{reviewed_at:%Y/%m/%d}/"
            f"{payload['feedback_id']}.json"
        )
        body = (json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
        self.store.write(key, body)
        return key


def feedback_service_from_environment(runtime_dir: Path) -> FeedbackService:
    bucket = os.environ.get("COURSEWARE_FEEDBACK_OSS_BUCKET", "").strip()
    if not bucket:
        return FeedbackService(LocalFeedbackStore(runtime_dir / "feedback"))
    region = os.environ.get("COURSEWARE_OSS_REGION", "cn-hangzhou").strip()
    endpoint = os.environ.get("COURSEWARE_OSS_ENDPOINT", "").strip() or None
    return FeedbackService(OssFeedbackStore(bucket, region, endpoint))
