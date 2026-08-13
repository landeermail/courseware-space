from __future__ import annotations

import http.client
import hashlib
import json
import os
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch


SERVER_DIR = Path(__file__).resolve().parents[1]
ROOT = SERVER_DIR.parent
sys.path.insert(0, str(SERVER_DIR))

from access_control import ACCESS_HEADER  # noqa: E402
from feedback_app import (  # noqa: E402
    FeedbackHandler,
    RequestRateLimiter,
    cors_origins_from_environment,
    feedback_services_from_environment,
    teacher_storage_key_from_environment,
)
from feedback_service import (  # noqa: E402
    FeedbackService,
    FeedbackStoreError,
    LocalFeedbackStore,
)
from review_workspace import TeacherReviewWorkspace  # noqa: E402

STRONG_CODE = "a1" * 24
OTHER_STRONG_CODE = "b2" * 24
STABLE_TEACHER_CODE = "Z9" * 24
ALLOWED_ORIGIN = "https://landeermail.github.io"
DENIED_ORIGIN = "https://evil.example.com"


def valid_payload() -> dict[str, object]:
    return json.loads((ROOT / "feedback" / "example.json").read_text(encoding="utf-8"))


def seed_workspace(root: Path, token: str) -> None:
    teacher_key = hashlib.sha256(token.encode("ascii")).hexdigest()
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
        path = root / f"feedback/tasks/{teacher_key}/{task['task_id']}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(task, ensure_ascii=False), encoding="utf-8")


class RunningServer:
    def __init__(
        self,
        service: FeedbackService,
        code: str = STRONG_CODE,
        per_client: int = 30,
        storage_key: str | None = None,
    ) -> None:
        from access_control import AccessCodeGate

        FeedbackHandler.cors_origins = frozenset({ALLOWED_ORIGIN})
        FeedbackHandler.rate_limiter = RequestRateLimiter(per_client=per_client, global_limit=80, window_seconds=600)
        FeedbackHandler.access_gate = AccessCodeGate(code)
        FeedbackHandler.feedback_service = service
        FeedbackHandler.review_workspace = TeacherReviewWorkspace(
            service.store, storage_key=storage_key
        )
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), FeedbackHandler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self) -> "RunningServer":
        self.thread.start()
        return self

    def __exit__(self, *args: object) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def request(
        self,
        method: str,
        path: str,
        payload: dict[str, object] | None = None,
        code: str | None = None,
        origin: str | None = None,
    ) -> tuple[int, dict[str, object] | None, str]:
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        headers: dict[str, str] = {}
        body: str | None = None
        if payload is not None:
            body = json.dumps(payload)
            headers["Content-Type"] = "application/json"
        if code is not None:
            headers[ACCESS_HEADER] = code
        if origin is not None:
            headers["Origin"] = origin
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        text = response.read().decode("utf-8")
        connection.close()
        parsed: dict[str, object] | None = None
        if text:
            parsed = json.loads(text)
        return response.status, parsed, text


class FeedbackOnlyHttpTests(unittest.TestCase):
    def test_reviews_require_the_single_stable_teacher_code(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store_root = Path(temporary)
            seed_workspace(store_root, STRONG_CODE)
            storage_key = hashlib.sha256(STRONG_CODE.encode("ascii")).hexdigest()
            service = FeedbackService(LocalFeedbackStore(store_root))
            with RunningServer(
                service, code=STABLE_TEACHER_CODE, storage_key=storage_key
            ) as running:
                accepted, workspace, _ = running.request(
                    "GET", "/api/reviews", code=STABLE_TEACHER_CODE, origin=ALLOWED_ORIGIN
                )
                rejected, _, _ = running.request(
                    "GET", "/api/reviews", code=STRONG_CODE, origin=ALLOWED_ORIGIN
                )

            self.assertEqual(accepted, 200)
            self.assertIsNotNone(workspace)
            self.assertEqual(rejected, 403)

    def test_health_is_public_feedback_only_and_has_no_provider(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            service = FeedbackService(LocalFeedbackStore(Path(temporary)))
            with RunningServer(service) as running:
                status, payload, raw = running.request("GET", "/api/health")
        self.assertEqual(status, 200)
        self.assertIsNotNone(payload)
        assert payload is not None
        self.assertEqual(payload["mode"], "feedback-only")
        self.assertEqual(payload["status"], "ok")
        self.assertNotIn("provider", payload)
        self.assertNotIn("provider", raw)

    def test_wrong_code_is_403_and_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store_root = Path(temporary)
            service = FeedbackService(LocalFeedbackStore(store_root))
            with RunningServer(service) as running:
                status, _, _ = running.request(
                    "POST", "/api/feedback", payload=valid_payload(), code=OTHER_STRONG_CODE
                )
            self.assertEqual(status, 403)
            self.assertEqual(list(store_root.rglob("*.json")), [])

    def test_invalid_payload_is_400_and_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store_root = Path(temporary)
            service = FeedbackService(LocalFeedbackStore(store_root))
            payload = valid_payload()
            del payload["dimensions"]["exam_connection"]  # type: ignore[index]
            with RunningServer(service) as running:
                status, _, _ = running.request("POST", "/api/feedback", payload=payload, code=STRONG_CODE)
            self.assertEqual(status, 400)
            self.assertEqual(list(store_root.rglob("*.json")), [])

    def test_store_failure_is_503(self) -> None:
        class FailingStore:
            backend = "local"

            def write(self, key: str, body: bytes) -> None:
                raise FeedbackStoreError("存储不可用")

        with RunningServer(FeedbackService(FailingStore())) as running:
            status, _, _ = running.request("POST", "/api/feedback", payload=valid_payload(), code=STRONG_CODE)
        self.assertEqual(status, 503)

    def test_valid_submission_is_201_and_writes_dated_key(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store_root = Path(temporary)
            service = FeedbackService(LocalFeedbackStore(store_root))
            payload = valid_payload()
            with RunningServer(service) as running:
                status, body, _ = running.request("POST", "/api/feedback", payload=payload, code=STRONG_CODE)
            self.assertEqual(status, 201)
            self.assertIsNotNone(body)
            assert body is not None
            expected_key = f"feedback/2026/07/30/{payload['feedback_id']}.json"
            self.assertEqual(body["object_key"], expected_key)
            written = json.loads((store_root / expected_key).read_text(encoding="utf-8"))
            self.assertEqual(written, payload)

    def test_personal_workspace_can_be_loaded_and_exact_task_submitted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store_root = Path(temporary)
            seed_workspace(store_root, STRONG_CODE)
            service = FeedbackService(LocalFeedbackStore(store_root))
            example = valid_payload()
            form = {"dimensions": example["dimensions"], "overall": example["overall"]}
            with RunningServer(service) as running:
                before, workspace, _ = running.request(
                    "GET", "/api/reviews", code=STRONG_CODE, origin=ALLOWED_ORIGIN
                )
                resolved_status, resolved, _ = running.request(
                    "GET",
                    "/api/reviews?courseware_id=q01-vertical-circle",
                    code=STRONG_CODE,
                    origin=ALLOWED_ORIGIN,
                )
                submitted, result, _ = running.request(
                    "POST",
                    "/api/reviews/q01-v8-teacher-review",
                    payload=form,
                    code=STRONG_CODE,
                    origin=ALLOWED_ORIGIN,
                )
                after, updated, _ = running.request(
                    "GET", "/api/reviews", code=STRONG_CODE, origin=ALLOWED_ORIGIN
                )

            self.assertEqual(before, 200)
            self.assertEqual(resolved_status, 200)
            self.assertEqual(submitted, 201)
            self.assertEqual(after, 200)
            assert workspace is not None and resolved is not None and result is not None and updated is not None
            self.assertEqual(workspace["tasks"][1]["status"], "pending")
            self.assertEqual(resolved["tasks"][0]["task_id"], "q01-v8-teacher-review")
            self.assertEqual(result["revision_id"], "q01-v8-1c89623d5bf0")
            self.assertEqual(updated["tasks"][1]["status"], "reviewed")

    def test_review_routes_reject_token_without_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            service = FeedbackService(LocalFeedbackStore(Path(temporary)))
            with RunningServer(service) as running:
                status, _, _ = running.request(
                    "GET", "/api/reviews", code=OTHER_STRONG_CODE, origin=ALLOWED_ORIGIN
                )
            self.assertEqual(status, 403)

    def test_review_reads_are_rate_limited_before_oss_lookup(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store_root = Path(temporary)
            seed_workspace(store_root, STRONG_CODE)
            service = FeedbackService(LocalFeedbackStore(store_root))
            with RunningServer(service, per_client=1) as running:
                first, _, _ = running.request("GET", "/api/reviews", code=STRONG_CODE)
                second, _, _ = running.request("GET", "/api/reviews", code=STRONG_CODE)
            self.assertEqual(first, 200)
            self.assertEqual(second, 429)

    def test_rate_limit_blocks_before_access_check(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            service = FeedbackService(LocalFeedbackStore(Path(temporary)))
            with RunningServer(service, per_client=1) as running:
                first, _, _ = running.request("POST", "/api/feedback", payload=valid_payload(), code=STRONG_CODE)
                second, _, _ = running.request("POST", "/api/feedback", payload=valid_payload(), code=OTHER_STRONG_CODE)
            self.assertEqual(first, 201)
            self.assertEqual(second, 429)

    def test_non_whitelist_origin_preflight_is_403(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            service = FeedbackService(LocalFeedbackStore(Path(temporary)))
            with RunningServer(service) as running:
                denied, _, _ = running.request("OPTIONS", "/api/feedback", origin=DENIED_ORIGIN)
                allowed, _, _ = running.request("OPTIONS", "/api/feedback", origin=ALLOWED_ORIGIN)
            self.assertEqual(denied, 403)
            self.assertEqual(allowed, 204)

    def test_all_generation_and_content_routes_are_404(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            service = FeedbackService(LocalFeedbackStore(Path(temporary)))
            with RunningServer(service) as running:
                for path in (
                    "/api/generate",
                    "/api/manual-requests",
                    "/api/media/parse",
                    "/api/media/confirm",
                    "/api/jobs/job-1",
                ):
                    status, _, _ = running.request("POST", path, payload=valid_payload(), code=STRONG_CODE)
                    self.assertEqual(status, 404, f"POST {path}")
                for path in (
                    "/api/generate",
                    "/api/jobs/job-1",
                    "/generated/anything/",
                    "/generator/",
                    "/generator/media/",
                    "/",
                ):
                    status, _, _ = running.request("GET", path, code=STRONG_CODE)
                    self.assertEqual(status, 404, f"GET {path}")


class StartupGateTests(unittest.TestCase):
    def test_storage_key_environment_requires_sha256(self) -> None:
        with patch.dict(
            os.environ,
            {"COURSEWARE_TEACHER_STORAGE_KEY": "c3" * 32},
            clear=True,
        ):
            self.assertEqual(teacher_storage_key_from_environment(), "c3" * 32)
        with patch.dict(
            os.environ,
            {"COURSEWARE_TEACHER_STORAGE_KEY": "weak"},
            clear=True,
        ):
            with self.assertRaisesRegex(RuntimeError, "STORAGE_KEY"):
                teacher_storage_key_from_environment()

    def test_starts_without_any_kimi_environment(self) -> None:
        env = {key: value for key, value in os.environ.items() if "KIMI" not in key.upper()}
        with patch.dict(os.environ, env, clear=True):
            with tempfile.TemporaryDirectory() as temporary:
                gate, service = feedback_services_from_environment(Path(temporary))
            self.assertFalse(gate.required)
            self.assertEqual(service.store.backend, "local")
            self.assertEqual(cors_origins_from_environment(), frozenset({"https://landeermail.github.io", "http://127.0.0.1:8000", "http://localhost:8000"}))

    def test_cloud_mode_refuses_to_start_without_access_code(self) -> None:
        with patch.dict(os.environ, {"COURSEWARE_CLOUD_MODE": "1"}, clear=True):
            with tempfile.TemporaryDirectory() as temporary:
                with self.assertRaisesRegex(RuntimeError, "ACCESS_CODE"):
                    feedback_services_from_environment(Path(temporary))

    def test_cloud_mode_refuses_to_start_with_weak_access_code(self) -> None:
        with patch.dict(
            os.environ,
            {"COURSEWARE_CLOUD_MODE": "1", "COURSEWARE_ACCESS_CODE": "weak", "COURSEWARE_FEEDBACK_OSS_BUCKET": "courseware-space-private-x1"},
            clear=True,
        ):
            with tempfile.TemporaryDirectory() as temporary:
                with self.assertRaisesRegex(RuntimeError, "48"):
                    feedback_services_from_environment(Path(temporary))

    def test_cloud_mode_refuses_to_start_without_feedback_bucket(self) -> None:
        with patch.dict(
            os.environ,
            {"COURSEWARE_CLOUD_MODE": "1", "COURSEWARE_ACCESS_CODE": STRONG_CODE},
            clear=True,
        ):
            with tempfile.TemporaryDirectory() as temporary:
                with self.assertRaisesRegex(RuntimeError, "FEEDBACK_OSS_BUCKET"):
                    feedback_services_from_environment(Path(temporary))

    def test_cloud_mode_refuses_to_start_without_teacher_storage_key(self) -> None:
        with patch.dict(
            os.environ,
            {
                "COURSEWARE_CLOUD_MODE": "1",
                "COURSEWARE_ACCESS_CODE": STRONG_CODE,
                "COURSEWARE_FEEDBACK_OSS_BUCKET": "courseware-space-private-x1",
            },
            clear=True,
        ):
            with tempfile.TemporaryDirectory() as temporary:
                with self.assertRaisesRegex(RuntimeError, "STORAGE_KEY"):
                    feedback_services_from_environment(Path(temporary))

    def test_cloud_mode_reaches_store_setup_with_code_and_private_bucket(self) -> None:
        with patch.dict(
            os.environ,
            {
                "COURSEWARE_CLOUD_MODE": "1",
                "COURSEWARE_ACCESS_CODE": STRONG_CODE,
                "COURSEWARE_FEEDBACK_OSS_BUCKET": "courseware-space-private-x1",
                "COURSEWARE_OSS_REGION": "cn-hangzhou",
                "COURSEWARE_TEACHER_STORAGE_KEY": "c3" * 32,
            },
            clear=True,
        ):
            with tempfile.TemporaryDirectory() as temporary:
                try:
                    gate, service = feedback_services_from_environment(Path(temporary))
                except FeedbackStoreError as error:
                    self.assertIn("alibabacloud-oss-v2", str(error))
                else:
                    self.assertTrue(gate.required)
                    self.assertEqual(service.store.backend, "oss")


if __name__ == "__main__":
    unittest.main()
