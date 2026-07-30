"""Validate anonymous courseware feedback and append it to private storage."""

from __future__ import annotations

from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import re
from typing import Any, Protocol


ROOT = Path(__file__).resolve().parent.parent
VALIDATOR_PATH = ROOT / "feedback" / "validate_feedback.py"
PRIVATE_BUCKET = re.compile(r"^courseware-space-private-[a-z0-9-]+$")


class FeedbackValidationError(ValueError):
    pass


class FeedbackStoreError(RuntimeError):
    pass


def _load_validator():
    spec = importlib.util.spec_from_file_location("courseware_feedback_validator", VALIDATOR_PATH)
    if spec is None or spec.loader is None:
        raise FeedbackStoreError("反馈校验器不可用")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.validate_feedback


validate_feedback = _load_validator()


class FeedbackStore(Protocol):
    backend: str

    def write(self, key: str, body: bytes) -> None:
        ...


class LocalFeedbackStore:
    backend = "local"

    def __init__(self, root: Path) -> None:
        self.root = root

    def write(self, key: str, body: bytes) -> None:
        target = (self.root / key).resolve()
        root = self.root.resolve()
        try:
            target.relative_to(root)
        except ValueError as error:
            raise FeedbackStoreError("反馈存储路径无效") from error
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            with target.open("xb") as stream:
                stream.write(body)
        except FileExistsError as error:
            raise FeedbackStoreError("反馈编号已存在") from error


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
        if not key.startswith("feedback/"):
            raise FeedbackStoreError("反馈 OSS 前缀无效")
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
