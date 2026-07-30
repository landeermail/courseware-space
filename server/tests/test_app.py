from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


SERVER_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER_DIR))

from app import DEFAULT_CORS_ORIGINS, RequestRateLimiter, cors_origins_from_environment  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
