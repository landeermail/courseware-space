import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock


MODULE_PATH = Path(__file__).with_name("private_delivery.py")
SPEC = importlib.util.spec_from_file_location("private_delivery", MODULE_PATH)
delivery = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(delivery)


class PrivateDeliveryTests(unittest.TestCase):
    def test_settings_refuse_any_other_cloud_resource(self) -> None:
        with mock.patch.dict(
            delivery.os.environ,
            {"COURSEWARE_PRIVATE_BUCKET": "courseware-space-demo-10794778"},
        ):
            with self.assertRaises(ValueError):
                delivery.settings()

    def test_policy_allows_only_private_objects_and_does_not_deny_runtime_listing(self) -> None:
        policy = delivery.policy_document(delivery.BUCKET, "1234567890123456")
        self.assertEqual(len(policy["Statement"]), 1)
        allow = policy["Statement"][0]
        self.assertEqual(allow["Effect"], "Allow")
        self.assertEqual(allow["Action"], ["oss:GetObject"])
        self.assertEqual(allow["Principal"], ["*"])
        self.assertEqual(
            allow["Resource"],
            [f"acs:oss:*:1234567890123456:{delivery.BUCKET}/private/*"],
        )
        policy_text = json.dumps(policy)
        self.assertNotIn("oss:ListObjects", policy_text)
        self.assertNotIn("oss:ListObjectVersions", policy_text)

    def test_random_token_is_url_safe_and_at_least_48_characters(self) -> None:
        for _ in range(20):
            self.assertRegex(delivery.random_token(), delivery.TOKEN_RE)

    def test_content_types_keep_html_inline_and_utf8(self) -> None:
        self.assertEqual(delivery.content_type("index.html"), "text/html; charset=utf-8")
        self.assertEqual(
            delivery.content_type("reference-data.json"),
            "application/json; charset=utf-8",
        )

    def test_existing_active_delivery_is_reused(self) -> None:
        payload = {
            "schema_version": 1,
            "deliveries": [
                {
                    "courseware_id": "q01-vertical-circle",
                    "bucket": delivery.BUCKET,
                    "active": True,
                    "token": "a" * 48,
                }
            ],
        }
        self.assertEqual(
            delivery.active_delivery(payload, "q01-vertical-circle")["token"],
            "a" * 48,
        )

    def test_new_delivery_deactivates_all_existing_active_records(self) -> None:
        payload = {
            "schema_version": 1,
            "deliveries": [
                {"courseware_id": "q01-vertical-circle", "active": True},
                {"courseware_id": "q01-vertical-circle", "active": True},
                {"courseware_id": "scoring-tool", "active": True},
            ],
        }

        self.assertEqual(
            delivery.deactivate_deliveries(payload, "q01-vertical-circle"), 2
        )
        self.assertEqual(
            [item["active"] for item in payload["deliveries"]],
            [False, False, True],
        )

    def test_delivery_record_file_must_have_expected_schema(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "deliveries.json"
            path.write_text(json.dumps({"schema_version": 2, "deliveries": []}))
            with self.assertRaises(ValueError):
                delivery.load_deliveries(path)


if __name__ == "__main__":
    unittest.main()
