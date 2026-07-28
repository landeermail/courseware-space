#!/usr/bin/env python3
"""Serve the static site and local generator API from one process."""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


SERVER_DIR = Path(__file__).resolve().parent
ROOT = SERVER_DIR.parent
sys.path.insert(0, str(SERVER_DIR))

from generator_service import GenerationManager, GenerationService, ManualRequestRecorder  # noqa: E402
from kimi_client import KimiCodeClient  # noqa: E402


def create_manager(runtime_dir: Path) -> GenerationManager:
    recorder = ManualRequestRecorder(runtime_dir / "manual-requests.jsonl")
    service = GenerationService(KimiCodeClient(), recorder)
    return GenerationManager(service, runtime_dir)


class GeneratorHandler(SimpleHTTPRequestHandler):
    manager: GenerationManager
    runtime_dir: Path

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, format: str, *args: object) -> None:
        print(f"{self.address_string()} - {format % args}")

    def _json(self, status: int, payload: dict[str, object]) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict[str, object]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as error:
            raise ValueError("Content-Length 无效") from error
        if not 1 <= length <= 65536:
            raise ValueError("请求体大小无效")
        try:
            data = json.loads(self.rfile.read(length))
        except json.JSONDecodeError as error:
            raise ValueError("请求体必须是 JSON") from error
        if not isinstance(data, dict):
            raise ValueError("请求体必须是 JSON 对象")
        return data

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            data = self._read_json()
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
            self._json(HTTPStatus.NOT_FOUND, {"error": "接口不存在"})
        except ValueError as error:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(error)})

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/health":
            self._json(
                HTTPStatus.OK,
                {
                    "status": "ok",
                    "provider": "kimi-code",
                    "provider_configured": self.manager.service.client.configured,
                },
            )
            return
        if path.startswith("/api/jobs/"):
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
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--runtime-dir",
        type=Path,
        default=Path(os.environ.get("COURSEWARE_RUNTIME_DIR", "/tmp/courseware-space-generator")),
    )
    args = parser.parse_args()
    args.runtime_dir.mkdir(parents=True, exist_ok=True)

    manager = create_manager(args.runtime_dir)
    GeneratorHandler.manager = manager
    GeneratorHandler.runtime_dir = args.runtime_dir
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
