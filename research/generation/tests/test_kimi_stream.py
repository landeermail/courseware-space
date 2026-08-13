from __future__ import annotations

import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


SERVER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER))

from research.generation.runtime.kimi_client import (  # noqa: E402
    KimiCodeClient,
    ProviderError,
    _classify_access_error,
    _read_sse_completion,
    _read_sse_content,
)


class KimiModelPolicyTests(unittest.TestCase):
    def test_k3_256k_model_is_allowed(self) -> None:
        client = KimiCodeClient(api_key="not-used")
        self.assertEqual(client.model, "k3-256k")
        self.assertEqual(client.reasoning_effort, "high")

    def test_highspeed_model_is_forbidden(self) -> None:
        with self.assertRaisesRegex(ValueError, "HighSpeed"):
            KimiCodeClient(api_key="not-used", model="kimi-for-coding-highspeed")

    def test_k2_7_fallback_is_forbidden(self) -> None:
        with self.assertRaisesRegex(ValueError, "k3-256k"):
            KimiCodeClient(api_key="not-used", model="kimi-for-coding")

    def test_request_payload_pins_k3_policy_without_sampling_overrides(self) -> None:
        body = json.dumps(
            {
                "id": "response-1",
                "model": "k3-256k",
                "choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 4, "total_tokens": 16},
            }
        ).encode()
        captured: list[object] = []

        def fake_urlopen(request: object, timeout: float) -> io.BytesIO:
            captured.append((request, timeout))
            return io.BytesIO(body)

        client = KimiCodeClient(api_key="not-used")
        with patch("research.generation.runtime.kimi_client.urllib.request.urlopen", side_effect=fake_urlopen):
            result = client.complete_result(
                "system",
                "user",
                phase="physics_model",
                prompt_cache_key="a" * 64,
            )
        request, timeout = captured[0]
        payload = json.loads(request.data)
        self.assertEqual(timeout, 120.0)
        self.assertEqual(payload["model"], "k3-256k")
        self.assertEqual(payload["reasoning_effort"], "high")
        self.assertEqual(payload["response_format"], {"type": "json_object"})
        self.assertEqual(payload["max_completion_tokens"], 32768)
        self.assertEqual(payload["prompt_cache_key"], "a" * 64)
        self.assertNotIn("temperature", payload)
        self.assertNotIn("top_p", payload)
        self.assertEqual(result.metadata["actual_model"], "k3-256k")
        self.assertEqual(result.metadata["usage"]["total_tokens"], 16)

    def test_length_limit_does_not_retry(self) -> None:
        body = json.dumps(
            {
                "model": "k3-256k",
                "choices": [{"message": {"content": "{\"partial\":"}, "finish_reason": "length"}],
            }
        ).encode()
        calls = 0

        def fake_urlopen(request: object, timeout: float) -> io.BytesIO:
            nonlocal calls
            calls += 1
            return io.BytesIO(body)

        client = KimiCodeClient(api_key="not-used", max_retries=1)
        with patch("research.generation.runtime.kimi_client.urllib.request.urlopen", side_effect=fake_urlopen):
            with self.assertRaises(ProviderError) as captured:
                client.complete("system", "user")
        self.assertEqual(captured.exception.kind, "length_limit")
        self.assertEqual(calls, 1)

    def test_read_timeout_does_not_retry(self) -> None:
        client = KimiCodeClient(api_key="not-used", max_retries=1)
        with patch("research.generation.runtime.kimi_client.urllib.request.urlopen", side_effect=TimeoutError("late")) as urlopen:
            with self.assertRaises(ProviderError) as captured:
                client.complete("system", "user")
        self.assertEqual(captured.exception.kind, "read_timeout")
        self.assertEqual(urlopen.call_count, 1)


class KimiStreamParserTests(unittest.TestCase):
    def test_openai_sse_deltas_are_joined(self) -> None:
        frames = [
            b': keep-alive\n',
            ("data: " + json.dumps({"choices": [{"delta": {"content": "hel"}}]}) + "\n").encode(),
            ("data: " + json.dumps({"choices": [{"delta": {"content": "lo"}}]}) + "\n").encode(),
            b'data: [DONE]\n',
        ]
        self.assertEqual(_read_sse_content(frames), "hello")

    def test_invalid_sse_json_is_rejected(self) -> None:
        with self.assertRaises(ProviderError):
            _read_sse_content([b'data: not-json\n'])

    def test_stream_metadata_and_numeric_usage_are_preserved(self) -> None:
        frames = [
            (
                "data: "
                + json.dumps(
                    {
                        "id": "response-1",
                        "model": "k3-256k",
                        "choices": [{"delta": {"content": "{}"}, "finish_reason": "stop"}],
                        "usage": {
                            "prompt_tokens": 10,
                            "completion_tokens": 3,
                            "prompt_tokens_details": {"cached_tokens": 4, "unsafe": "drop"},
                        },
                    }
                )
                + "\n"
            ).encode(),
            b"data: [DONE]\n",
        ]
        parsed = _read_sse_completion(frames)
        self.assertEqual(parsed.content, "{}")
        self.assertEqual(parsed.response_id, "response-1")
        self.assertEqual(parsed.model, "k3-256k")
        self.assertEqual(parsed.finish_reason, "stop")
        self.assertEqual(parsed.usage["prompt_tokens_details"], {"cached_tokens": 4})


class KimiAccessErrorTests(unittest.TestCase):
    def test_401_is_authentication(self) -> None:
        error = _classify_access_error(401, '{"message":"invalid token"}')
        self.assertIsNotNone(error)
        self.assertEqual(error.kind, "authentication")
        self.assertNotIn("invalid token", str(error))

    def test_403_quota_body_is_safely_classified(self) -> None:
        error = _classify_access_error(403, '{"message":"monthly usage limit reached"}')
        self.assertIsNotNone(error)
        self.assertEqual(error.kind, "quota")
        self.assertNotIn("monthly usage", str(error))

    def test_other_403_is_permission(self) -> None:
        error = _classify_access_error(403, '{"message":"account not allowed"}')
        self.assertIsNotNone(error)
        self.assertEqual(error.kind, "permission")

    def test_other_status_is_not_access_error(self) -> None:
        self.assertIsNone(_classify_access_error(500, "server error"))

    def test_429_quota_is_classified_without_provider_body(self) -> None:
        error = _classify_access_error(429, '{"message":"rate limit reached"}')
        self.assertIsNotNone(error)
        self.assertEqual(error.kind, "quota")
        self.assertNotIn("rate limit", str(error))
