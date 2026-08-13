from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPOSITORY_ROOT))

from research.generation.runtime.access_control import ACCESS_HEADER, AccessCodeGate  # noqa: E402
from research.generation.app import (  # noqa: E402
    DEFAULT_CORS_ORIGINS,
    GeneratorHandler,
    RequestRateLimiter,
    cors_origins_from_environment,
)

STRONG_CODE = "a1" * 24
OTHER_STRONG_CODE = "b2" * 24


class RequestRateLimiterTests(unittest.TestCase):
    def test_per_client_and_window_limits(self) -> None:
        limiter = RequestRateLimiter(per_client=2, global_limit=4, window_seconds=10)
        self.assertTrue(limiter.allow("teacher-a", now=0))
        self.assertTrue(limiter.allow("teacher-a", now=1))
        self.assertFalse(limiter.allow("teacher-a", now=2))
        self.assertTrue(limiter.allow("teacher-a", now=11))

    def test_global_limit_cannot_be_bypassed_with_more_client_keys(self) -> None:
        limiter = RequestRateLimiter(per_client=2, global_limit=3, window_seconds=10)
        self.assertTrue(limiter.allow("teacher-a", now=0))
        self.assertTrue(limiter.allow("teacher-b", now=1))
        self.assertTrue(limiter.allow("teacher-c", now=2))
        self.assertFalse(limiter.allow("teacher-d", now=3))


class CorsConfigurationTests(unittest.TestCase):
    def test_default_origins_include_pages_and_local_preview(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(cors_origins_from_environment(), DEFAULT_CORS_ORIGINS)
        self.assertIn("https://landeermail.github.io", DEFAULT_CORS_ORIGINS)

    def test_custom_origins_are_strict_http_origins(self) -> None:
        with patch.dict(
            os.environ,
            {"COURSEWARE_CORS_ORIGINS": "https://example.edu.cn,http://127.0.0.1:8000"},
            clear=True,
        ):
            self.assertEqual(
                cors_origins_from_environment(),
                frozenset({"https://example.edu.cn", "http://127.0.0.1:8000"}),
            )
        with patch.dict(os.environ, {"COURSEWARE_CORS_ORIGINS": "javascript:alert(1)"}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "HTTP"):
                cors_origins_from_environment()


class AccessOrderingTests(unittest.TestCase):
    def test_wrong_code_counts_toward_rate_limit_before_body_or_manager(self) -> None:
        handler = object.__new__(GeneratorHandler)
        handler.path = "/api/generate"
        handler.headers = {ACCESS_HEADER: OTHER_STRONG_CODE}
        handler.access_gate = AccessCodeGate(STRONG_CODE)
        events: list[str] = []
        handler._json = lambda status, payload: events.append(f"response:{status}")  # type: ignore[method-assign]
        handler._rate_limit_ok = lambda path: events.append("rate-limit") or True  # type: ignore[method-assign]
        handler._read_json = lambda max_bytes=65536: events.append("read-body") or {"question": "x"}  # type: ignore[method-assign]

        GeneratorHandler.do_POST(handler)

        self.assertEqual(events, ["rate-limit", "response:403"])

    def test_correct_code_reaches_request_body(self) -> None:
        handler = object.__new__(GeneratorHandler)
        handler.path = "/api/generate"
        handler.headers = {ACCESS_HEADER: STRONG_CODE}
        handler.access_gate = AccessCodeGate(STRONG_CODE)
        handler.manager = type("Manager", (), {"submit": lambda self, question: {"id": "job"}})()
        events: list[str] = []
        handler._json = lambda status, payload: events.append(f"response:{status}")  # type: ignore[method-assign]
        handler._rate_limit_ok = lambda path: events.append("rate-limit") or True  # type: ignore[method-assign]
        handler._read_json = lambda max_bytes=65536: events.append("read-body") or {"question": "x"}  # type: ignore[method-assign]

        GeneratorHandler.do_POST(handler)

        self.assertEqual(events, ["rate-limit", "read-body", "response:202"])

    def test_exhausted_rate_limit_stops_before_access_and_body(self) -> None:
        handler = object.__new__(GeneratorHandler)
        handler.path = "/api/generate"
        handler.headers = {ACCESS_HEADER: OTHER_STRONG_CODE}
        events: list[str] = []
        handler._rate_limit_ok = lambda path: events.append("rate-limit:blocked") or False  # type: ignore[method-assign]
        handler._access_ok = lambda: events.append("access") or False  # type: ignore[method-assign]
        handler._read_json = lambda max_bytes=65536: events.append("read-body") or {}  # type: ignore[method-assign]

        GeneratorHandler.do_POST(handler)

        self.assertEqual(events, ["rate-limit:blocked"])

    def test_feedback_api_is_not_owned_by_generation(self) -> None:
        handler = object.__new__(GeneratorHandler)
        handler.path = "/api/feedback"
        handler.headers = {}
        responses: list[int] = []
        handler._json = lambda status, payload: responses.append(status)  # type: ignore[method-assign]
        handler._rate_limit_ok = lambda path: True  # type: ignore[method-assign]
        handler._read_json = lambda max_bytes=65536: {}  # type: ignore[method-assign]

        GeneratorHandler.do_POST(handler)

        self.assertEqual(responses, [404])


if __name__ == "__main__":
    unittest.main()
