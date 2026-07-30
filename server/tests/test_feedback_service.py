from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


SERVER_DIR = Path(__file__).resolve().parents[1]
ROOT = SERVER_DIR.parent
sys.path.insert(0, str(SERVER_DIR))

from feedback_service import (  # noqa: E402
    FeedbackService,
    FeedbackStoreError,
    FeedbackValidationError,
    LocalFeedbackStore,
    OssFeedbackStore,
)


def valid_payload() -> dict[str, object]:
    return json.loads((ROOT / "feedback" / "example.json").read_text(encoding="utf-8"))


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


if __name__ == "__main__":
    unittest.main()
