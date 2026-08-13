#!/usr/bin/env python3
"""Serve the static site and local generator API from one process."""

from __future__ import annotations

import argparse
import importlib.util
import json
import mimetypes
import os
import shutil
import socket
import sys
import threading
import time
from collections import deque
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


MODULE_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = MODULE_ROOT.parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))

from research.generation.runtime.generator_service import (  # noqa: E402
    GenerationManager,
    GenerationService,
    ManualRequestRecorder,
)
from research.generation.runtime.kimi_client import KimiCodeClient, ProviderError  # noqa: E402
from research.generation.runtime.media_service import (  # noqa: E402
    MediaConfirmationWorkflow,
    MediaError,
    MediaParser,
)
from research.generation.runtime.artifact_store import artifact_store_from_environment  # noqa: E402
from research.generation.runtime.access_control import ACCESS_HEADER, AccessCodeGate  # noqa: E402


DEFAULT_CORS_ORIGINS = frozenset(
    {
        "https://landeermail.github.io",
        "http://127.0.0.1:8000",
        "http://localhost:8000",
    }
)
RATE_LIMITED_PATHS = frozenset(
    {
        "/api/generate",
        "/api/manual-requests",
        "/api/media/parse",
        "/api/media/confirm",
    }
)
PROTECTED_POST_PATHS = RATE_LIMITED_PATHS


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
        raise RuntimeError("课件生成限流环境变量无效") from error


def create_manager(runtime_dir: Path) -> GenerationManager:
    recorder = ManualRequestRecorder(runtime_dir / "manual-requests.jsonl")
    service = GenerationService(KimiCodeClient(), recorder)
    try:
        max_workers = int(os.environ.get("COURSEWARE_MAX_WORKERS", "2"))
    except ValueError as error:
        raise RuntimeError("COURSEWARE_MAX_WORKERS 必须是整数") from error
    if not 1 <= max_workers <= 4:
        raise RuntimeError("COURSEWARE_MAX_WORKERS 必须在 1～4")
    return GenerationManager(
        service,
        runtime_dir,
        max_workers=max_workers,
        artifact_store=artifact_store_from_environment(),
    )


class GeneratorHandler(SimpleHTTPRequestHandler):
    manager: GenerationManager
    media_workflow: MediaConfirmationWorkflow
    runtime_dir: Path
    cors_origins: frozenset[str]
    rate_limiter: RequestRateLimiter
    access_gate: AccessCodeGate

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, directory=str(MODULE_ROOT), **kwargs)

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
        if path not in RATE_LIMITED_PATHS:
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
        if not self._rate_limit_ok(path):
            return
        if path in PROTECTED_POST_PATHS and not self._access_ok():
            return
        try:
            data = self._read_json(28 * 1024 * 1024 if path == "/api/media/parse" else 65536)
            if path == "/api/generate":
                if set(data) != {"question"}:
                    raise ValueError("生成请求只允许 question 字段")
                job = self.manager.submit(data["question"])
                self._json(HTTPStatus.ACCEPTED, {"job": job})
                return
            if path == "/api/manual-requests":
                if not {"job_id", "name", "contact"} <= set(data) <= {"job_id", "name", "contact", "note"}:
                    raise ValueError("人工请求字段不完整")
                self.manager.record_contact(
                    str(data["job_id"]),
                    data["name"],
                    data["contact"],
                    data.get("note", ""),
                )
                self._json(HTTPStatus.CREATED, {"status": "accepted", "delivery": "24 小时内人工交付"})
                return
            if path == "/api/media/parse":
                if set(data) != {"filename", "mime_type", "data_base64"}:
                    raise ValueError("上传请求字段不符合白名单")
                parsed = self.media_workflow.parse_upload(
                    data["filename"],
                    data["mime_type"],
                    data["data_base64"],
                )
                self._json(HTTPStatus.CREATED, {"parse": parsed})
                return
            if path == "/api/media/confirm":
                result = self.media_workflow.confirm_and_submit(data)
                self._json(HTTPStatus.ACCEPTED, result)
                return
            self._json(HTTPStatus.NOT_FOUND, {"error": "接口不存在"})
        except (ValueError, MediaError) as error:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
        except ProviderError as error:
            self._json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": str(error)})

    def do_OPTIONS(self) -> None:
        path = urlparse(self.path).path
        origin = self.headers.get("Origin", "").strip()
        if not path.startswith("/api/"):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if origin not in self.cors_origins:
            self._json(HTTPStatus.FORBIDDEN, {"error": "该来源不允许跨域调用生成服务"})
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
        path = urlparse(self.path).path
        if path == "/" and os.environ.get("COURSEWARE_CLOUD_MODE") == "1":
            self.send_response(HTTPStatus.FOUND)
            self.send_header("Location", "/generator/")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return
        if path == "/api/health":
            self._json(
                HTTPStatus.OK,
                {
                    "status": "ok",
                    "provider": "kimi-code",
                    "provider_configured": self.manager.service.client.configured,
                    "media_confirmation_gate": True,
                    "pdf_parser_configured": bool(
                        importlib.util.find_spec("pypdfium2") or shutil.which("pdftoppm")
                    ),
                    "artifact_store": self.manager.artifact_store.backend,
                    "access_code_required": self.access_gate.required,
                },
            )
            return
        if path == "/generator/media/":
            self._serve_media_demo()
            return
        if path.startswith("/api/jobs/"):
            if not self._access_ok():
                return
            job_id = path.removeprefix("/api/jobs/").strip("/")
            if not job_id or "/" in job_id:
                self._json(HTTPStatus.NOT_FOUND, {"error": "任务不存在"})
                return
            job = self.manager.get(job_id)
            if not job:
                self._json(HTTPStatus.NOT_FOUND, {"error": "任务不存在"})
                return
            self._json(HTTPStatus.OK, {"job": job})
            return
        if path.startswith("/generated/"):
            self._serve_generated(path)
            return
        super().do_GET()

    def _serve_media_demo(self) -> None:
        candidate = MODULE_ROOT / "generator" / "media.html"
        content = candidate.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(content)

    def _serve_generated(self, request_path: str) -> None:
        relative = request_path.removeprefix("/generated/")
        candidate = (self.runtime_dir / "generated" / relative).resolve()
        root = (self.runtime_dir / "generated").resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if candidate.is_dir():
            candidate = candidate / "index.html"
        if not candidate.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content = candidate.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mimetypes.guess_type(candidate.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(content)


def main() -> int:
    parser = argparse.ArgumentParser()
    cloud_port = os.environ.get("FC_CUSTOM_LISTEN_PORT", "").strip()
    parser.add_argument("--host", default="0.0.0.0" if cloud_port else "127.0.0.1")
    parser.add_argument("--port", type=int, default=int(cloud_port or "8000"))
    parser.add_argument(
        "--runtime-dir",
        type=Path,
        default=Path(os.environ.get("COURSEWARE_RUNTIME_DIR", "/tmp/courseware-space-generator")),
    )
    args = parser.parse_args()
    args.runtime_dir.mkdir(parents=True, exist_ok=True)

    manager = create_manager(args.runtime_dir)
    GeneratorHandler.manager = manager
    GeneratorHandler.media_workflow = MediaConfirmationWorkflow(MediaParser(manager.service.client), manager)
    GeneratorHandler.runtime_dir = args.runtime_dir
    GeneratorHandler.cors_origins = cors_origins_from_environment()
    GeneratorHandler.rate_limiter = rate_limiter_from_environment()
    GeneratorHandler.access_gate = AccessCodeGate.from_environment()
    server = ThreadingHTTPServer((args.host, args.port), GeneratorHandler)
    print(f"Courseware generator: http://{args.host}:{args.port}/generator/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        manager.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
