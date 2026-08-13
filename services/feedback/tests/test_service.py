from __future__ import annotations

import json
import io
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from services.feedback.service import (  # noqa: E402
    FeedbackService,
    FeedbackStoreError,
    FeedbackValidationError,
    LocalFeedbackStore,
    OssFeedbackStore,
)


def valid_payload() -> dict[str, object]:
    return json.loads((ROOT / "services" / "feedback" / "schema" / "example.json").read_text(encoding="utf-8"))


class FeedbackServiceTests(unittest.TestCase):
    def test_valid_feedback_is_written_under_dated_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            payload = valid_payload()
            service = FeedbackService(LocalFeedbackStore(root))

            key = service.submit(payload)

            self.assertEqual(key, f"feedback/2026/07/30/{payload['feedback_id']}.json")
            written = json.loads((root / key).read_text(encoding="utf-8"))
            self.assertEqual(written, payload)

    def test_invalid_feedback_is_rejected_before_write(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            payload = valid_payload()
            del payload["dimensions"]["exam_connection"]  # type: ignore[index]
            service = FeedbackService(LocalFeedbackStore(root))

            with self.assertRaises(FeedbackValidationError):
                service.submit(payload)

            self.assertFalse(any(root.rglob("*.json")))

    def test_duplicate_feedback_id_cannot_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            service = FeedbackService(LocalFeedbackStore(Path(temporary)))
            payload = valid_payload()
            service.submit(payload)

            with self.assertRaisesRegex(FeedbackStoreError, "已存在"):
                service.submit(payload)

    def test_oss_store_rejects_non_private_bucket_before_sdk_setup(self) -> None:
        with self.assertRaisesRegex(FeedbackStoreError, "private"):
            OssFeedbackStore("courseware-space-demo-123", "cn-hangzhou")

    def test_oss_store_reads_and_lists_only_feedback_prefix_with_pagination(self) -> None:
        class Request:
            def __init__(self, **kwargs: object) -> None:
                vars(self).update(kwargs)

        class Client:
            def __init__(self, _config: object) -> None:
                self.list_requests: list[object] = []

            def get_object(self, request: object) -> object:
                self.get_request = request
                return SimpleNamespace(status_code=200, body=io.BytesIO(b'{"ok":true}'))

            def list_objects_v2(self, request: object) -> object:
                self.list_requests.append(request)
                if len(self.list_requests) == 1:
                    return SimpleNamespace(
                        status_code=200,
                        contents=[SimpleNamespace(key="feedback/reviews/t/task/a.json")],
                        is_truncated=True,
                        next_continuation_token="next",
                    )
                return SimpleNamespace(
                    status_code=200,
                    contents=[SimpleNamespace(key="feedback/reviews/t/task/b.json")],
                    is_truncated=False,
                    next_continuation_token=None,
                )

        fake_sdk = SimpleNamespace(
            credentials=SimpleNamespace(EnvironmentVariableCredentialsProvider=lambda: object()),
            config=SimpleNamespace(load_default=lambda: SimpleNamespace()),
            Client=Client,
            GetObjectRequest=Request,
            ListObjectsV2Request=Request,
            PutObjectRequest=Request,
        )
        with patch.dict(sys.modules, {"alibabacloud_oss_v2": fake_sdk}):
            store = OssFeedbackStore("courseware-space-private-x1", "cn-hangzhou")

        body = store.read("feedback/reviews/t/task/a.json")
        keys = store.list("feedback/reviews/t/task/")

        self.assertEqual(body, b'{"ok":true}')
        self.assertEqual(
            keys,
            ["feedback/reviews/t/task/a.json", "feedback/reviews/t/task/b.json"],
        )
        self.assertEqual(store.client.get_request.key, "feedback/reviews/t/task/a.json")
        self.assertEqual(
            [request.prefix for request in store.client.list_requests],
            ["feedback/reviews/t/task/", "feedback/reviews/t/task/"],
        )
        self.assertEqual(store.client.list_requests[1].continuation_token, "next")

    def test_oss_store_rejects_read_or_list_outside_feedback_prefix(self) -> None:
        store = object.__new__(OssFeedbackStore)
        with self.assertRaisesRegex(FeedbackStoreError, "前缀"):
            store.read("private/teacher.json")
        with self.assertRaisesRegex(FeedbackStoreError, "前缀"):
            store.list("private/")


if __name__ == "__main__":
    unittest.main()
