#!/usr/bin/env python3
"""Feedback-only HTTP service: no generator, media, templates, or model credentials.

Cloud mode refuses to start without a valid 48-char access code and a private
feedback OSS bucket. GET /api/health is public; the legacy POST /api/feedback
keeps its shared access gate. Teacher-scoped /api/reviews routes use the same
header shape as a personal token and authorize it by an existing private
workspace object. Every other route is 404.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
import sys
import threading
import time
from collections import deque
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


MODULE_DIR = Path(__file__).resolve().parent
ROOT = MODULE_DIR.parents[1]
sys.path.insert(0, str(ROOT))

from services.feedback.access_control import ACCESS_HEADER, AccessCodeGate  # noqa: E402
from services.feedback.service import (  # noqa: E402
    FeedbackService,
    FeedbackStoreError,
    FeedbackValidationError,
    feedback_service_from_environment,
)
from services.feedback.review_workspace import (  # noqa: E402
    ReviewAccessError,
    ReviewClosedError,
    ReviewDataError,
    TeacherReviewWorkspace,
    apply_task_dispositions,
    apply_teacher_feedback_updates,
)


DEFAULT_CORS_ORIGINS = frozenset(
    {
        "https://landeermail.github.io",
        "http://127.0.0.1:8000",
        "http://localhost:8000",
    }
)
FEEDBACK_PATH = "/api/feedback"
REVIEWS_PATH = "/api/reviews"
STORAGE_KEY_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def cors_origins_from_environment() -> frozenset[str]:
    configured = os.environ.get("COURSEWARE_CORS_ORIGINS", "").strip()
    if not configured:
        return DEFAULT_CORS_ORIGINS
    origins = frozenset(item.strip() for item in configured.split(",") if item.strip())
    if not origins or any(not item.startswith(("https://", "http://")) for item in origins):
        raise RuntimeError("COURSEWARE_CORS_ORIGINS 必须是逗号分隔的 HTTP(S) Origin")
    return origins


class RequestRateLimiter:
    """Small in-process cost guard; FC concurrency remains the account-level backstop."""

    def __init__(self, per_client: int = 30, global_limit: int = 80, window_seconds: int = 600) -> None:
        if not 1 <= per_client <= global_limit or window_seconds < 1:
            raise ValueError("限流参数无效")
        self.per_client = per_client
        self.global_limit = global_limit
        self.window_seconds = window_seconds
        self._global: deque[float] = deque()
        self._clients: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def allow(self, client: str, now: float | None = None) -> bool:
        current = time.monotonic() if now is None else now
        cutoff = current - self.window_seconds
        with self._lock:
            while self._global and self._global[0] <= cutoff:
                self._global.popleft()
            bucket = self._clients.get(client)
            if bucket is None:
                if len(self._clients) >= 2048:
                    return False
                bucket = deque()
                self._clients[client] = bucket
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= self.per_client or len(self._global) >= self.global_limit:
                return False
            bucket.append(current)
            self._global.append(current)
            return True


def rate_limiter_from_environment() -> RequestRateLimiter:
    try:
        return RequestRateLimiter(
            per_client=int(os.environ.get("COURSEWARE_RATE_LIMIT_PER_CLIENT", "30")),
            global_limit=int(os.environ.get("COURSEWARE_RATE_LIMIT_GLOBAL", "80")),
            window_seconds=int(os.environ.get("COURSEWARE_RATE_LIMIT_WINDOW", "600")),
        )
    except ValueError as error:
        raise RuntimeError("课件评价限流环境变量无效") from error


def cloud_mode_enabled() -> bool:
    return os.environ.get("COURSEWARE_CLOUD_MODE") == "1"


def teacher_storage_key_from_environment() -> str | None:
    value = os.environ.get("COURSEWARE_TEACHER_STORAGE_KEY", "").strip()
    if value and not STORAGE_KEY_PATTERN.fullmatch(value):
        raise RuntimeError("COURSEWARE_TEACHER_STORAGE_KEY 必须是 SHA-256")
    return value or None


def review_dispositions_from_environment() -> list[dict[str, object]]:
    raw = os.environ.get("COURSEWARE_REVIEW_DISPOSITIONS_JSON", "").strip()
    if not raw:
        return []
    if len(raw.encode("utf-8")) > 16384:
        raise RuntimeError("COURSEWARE_REVIEW_DISPOSITIONS_JSON 过大")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        raise RuntimeError("COURSEWARE_REVIEW_DISPOSITIONS_JSON 必须是 JSON") from error
    if not isinstance(value, list) or not 1 <= len(value) <= 10 or not all(
        isinstance(item, dict) for item in value
    ):
        raise RuntimeError("COURSEWARE_REVIEW_DISPOSITIONS_JSON 必须包含 1 至 10 个对象")
    return value


def review_updates_from_environment() -> list[dict[str, object]]:
    raw = os.environ.get("COURSEWARE_REVIEW_UPDATES_JSON", "").strip()
    if not raw:
        return []
    if len(raw.encode("utf-8")) > 32768:
        raise RuntimeError("COURSEWARE_REVIEW_UPDATES_JSON 过大")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        raise RuntimeError("COURSEWARE_REVIEW_UPDATES_JSON 必须是 JSON") from error
    if not isinstance(value, list) or not 1 <= len(value) <= 10 or not all(
        isinstance(item, dict) for item in value
    ):
        raise RuntimeError("COURSEWARE_REVIEW_UPDATES_JSON 必须包含 1 至 10 个对象")
    return value


def feedback_services_from_environment(runtime_dir: Path) -> tuple[AccessCodeGate, FeedbackService]:
    """Build the gate and service; cloud mode fails closed without both prerequisites."""

    gate = AccessCodeGate.from_environment()
    if cloud_mode_enabled():
        bucket = os.environ.get("COURSEWARE_FEEDBACK_OSS_BUCKET", "").strip()
        if not bucket:
            raise RuntimeError("云端 feedback-only 运行必须设置 COURSEWARE_FEEDBACK_OSS_BUCKET")
        if not teacher_storage_key_from_environment():
            raise RuntimeError("云端评价工作区必须设置 COURSEWARE_TEACHER_STORAGE_KEY")
    return gate, feedback_service_from_environment(runtime_dir)


class FeedbackHandler(BaseHTTPRequestHandler):
    cors_origins: frozenset[str]
    rate_limiter: RequestRateLimiter
    access_gate: AccessCodeGate
    feedback_service: FeedbackService
    review_workspace: TeacherReviewWorkspace

    server_version = "CoursewareFeedbackOnly/1.0"

    def log_message(self, format: str, *args: object) -> None:
        print(f"{self.address_string()} - {format % args}")

    def _json(self, status: int, payload: dict[str, object]) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _send_cors_headers(self) -> None:
        origin = self.headers.get("Origin", "").strip()
        if origin in self.cors_origins:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")

    def _client_key(self) -> str:
        forwarded = self.headers.get("X-Forwarded-For", "").split(",", 1)[0].strip()
        candidate = forwarded or self.client_address[0]
        return candidate[:64]

    def _rate_limit_ok(self, path: str) -> bool:
        if path not in {FEEDBACK_PATH, REVIEWS_PATH} and not path.startswith(f"{REVIEWS_PATH}/"):
            return True
        if self.rate_limiter.allow(self._client_key()):
            return True
        self._json(HTTPStatus.TOO_MANY_REQUESTS, {"error": "请求过于频繁，请十分钟后再试。"})
        return False

    def _access_ok(self) -> bool:
        if self.access_gate.allows(self.headers.get(ACCESS_HEADER)):
            return True
        self._json(HTTPStatus.FORBIDDEN, {"error": "访问码无效"})
        return False

    def _personal_token(self) -> str:
        return self.headers.get(ACCESS_HEADER, "")

    def _read_json(self, max_bytes: int = 65536) -> dict[str, object]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as error:
            raise ValueError("Content-Length 无效") from error
        if not 1 <= length <= max_bytes:
            raise ValueError("请求体大小无效")
        chunks: list[bytes] = []
        remaining = length
        try:
            while remaining:
                chunk = self.rfile.read(min(65536, remaining))
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
        except (TimeoutError, socket.timeout) as error:
            received = length - remaining
            raise ValueError(f"请求体传输不完整（声明 {length} B，收到 {received} B）") from error
        if remaining:
            raise ValueError(f"请求体传输不完整（声明 {length} B，收到 {length - remaining} B）")
        try:
            data = json.loads(b"".join(chunks))
        except json.JSONDecodeError as error:
            raise ValueError("请求体必须是 JSON") from error
        if not isinstance(data, dict):
            raise ValueError("请求体必须是 JSON 对象")
        return data

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == FEEDBACK_PATH:
            if not self._rate_limit_ok(path):
                return
            if not self._access_ok():
                return
            try:
                data = self._read_json()
                key = self.feedback_service.submit(data)
                self._json(
                    HTTPStatus.CREATED,
                    {"status": "accepted", "feedback_id": data["feedback_id"], "object_key": key},
                )
            except (ValueError, FeedbackValidationError) as error:
                self._json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
            except FeedbackStoreError:
                self._json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "反馈暂时无法保存，请稍后再试。"})
            return
        if not path.startswith(f"{REVIEWS_PATH}/"):
            self._json(HTTPStatus.NOT_FOUND, {"error": "接口不存在"})
            return
        if not self._rate_limit_ok(path):
            return
        if not self._access_ok():
            return
        task_id = path[len(REVIEWS_PATH) + 1 :]
        if not task_id or "/" in task_id:
            self._json(HTTPStatus.NOT_FOUND, {"error": "接口不存在"})
            return
        try:
            data = self._read_json()
            result = self.review_workspace.submit(self._personal_token(), task_id, data)
            self._json(HTTPStatus.CREATED, result)
        except ReviewClosedError:
            self._json(HTTPStatus.CONFLICT, {"error": "评价任务已结束，无需补填"})
        except ReviewAccessError:
            self._json(HTTPStatus.FORBIDDEN, {"error": "个人链接无效或评价任务不存在"})
        except (ValueError, FeedbackValidationError) as error:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
        except (FeedbackStoreError, ReviewDataError):
            self._json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "反馈暂时无法保存，请稍后再试。"})

    def do_OPTIONS(self) -> None:
        path = urlparse(self.path).path
        origin = self.headers.get("Origin", "").strip()
        if not path.startswith("/api/"):
            self._json(HTTPStatus.NOT_FOUND, {"error": "接口不存在"})
            return
        if origin not in self.cors_origins:
            self._json(HTTPStatus.FORBIDDEN, {"error": "该来源不允许跨域调用评价服务"})
            return
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Content-Length", "0")
        self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", f"Content-Type, {ACCESS_HEADER}")
        self.send_header("Access-Control-Max-Age", "3600")
        self.send_header("Vary", "Origin")
        self.end_headers()

    def do_GET(self) -> None:
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        if path == "/api/health":
            self._json(
                HTTPStatus.OK,
                {
                    "status": "ok",
                    "mode": "feedback-only",
                    "feedback_store": self.feedback_service.store.backend,
                    "access_code_required": self.access_gate.required,
                },
            )
            return
        if path == REVIEWS_PATH:
            if not self._rate_limit_ok(path):
                return
            if not self._access_ok():
                return
            try:
                query = dict(
                    part.split("=", 1) if "=" in part else (part, "")
                    for part in parsed_url.query.split("&")
                    if part
                )
                courseware_id = query.get("courseware_id") or None
                workspace = self.review_workspace.load(
                    self._personal_token(), courseware_id=courseware_id
                )
                self._json(HTTPStatus.OK, workspace)
            except ReviewAccessError:
                self._json(HTTPStatus.FORBIDDEN, {"error": "个人链接无效"})
            except (FeedbackStoreError, ReviewDataError):
                self._json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "评价记录暂时无法读取，请稍后再试。"})
            return
        self._json(HTTPStatus.NOT_FOUND, {"error": "接口不存在"})


def main() -> int:
    parser = argparse.ArgumentParser()
    cloud_port = os.environ.get("FC_CUSTOM_LISTEN_PORT", "").strip()
    parser.add_argument("--host", default="0.0.0.0" if cloud_port else "127.0.0.1")
    parser.add_argument("--port", type=int, default=int(cloud_port or "8000"))
    parser.add_argument(
        "--runtime-dir",
        type=Path,
        default=Path(os.environ.get("COURSEWARE_RUNTIME_DIR", "/tmp/courseware-space-feedback")),
    )
    args = parser.parse_args()
    args.runtime_dir.mkdir(parents=True, exist_ok=True)

    gate, service = feedback_services_from_environment(args.runtime_dir)
    FeedbackHandler.cors_origins = cors_origins_from_environment()
    FeedbackHandler.rate_limiter = rate_limiter_from_environment()
    FeedbackHandler.access_gate = gate
    FeedbackHandler.feedback_service = service
    storage_key = teacher_storage_key_from_environment()
    updates = review_updates_from_environment()
    if updates:
        if not storage_key:
            raise RuntimeError("老师反馈更新需要现有老师存储键")
        result = apply_teacher_feedback_updates(service.store, storage_key, updates)
        print(
            "Teacher feedback updates: "
            f"written={result['written']} existing={result['existing']}"
        )
    dispositions = review_dispositions_from_environment()
    if dispositions:
        if not storage_key:
            raise RuntimeError("任务处置需要现有老师存储键")
        result = apply_task_dispositions(service.store, storage_key, dispositions)
        print(
            "Teacher review dispositions: "
            f"written={result['written']} existing={result['existing']}"
        )
    FeedbackHandler.review_workspace = TeacherReviewWorkspace(
        service.store,
        storage_key=storage_key,
    )
    server = ThreadingHTTPServer((args.host, args.port), FeedbackHandler)
    print(f"Courseware feedback-only service: http://{args.host}:{args.port}/api/health")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
