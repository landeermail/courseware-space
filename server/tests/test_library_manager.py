from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


SERVER_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER_DIR))

from library_manager import LibraryManager, MetadataError, validate_catalog, validate_metadata  # noqa: E402


def candidate_metadata(owner: str = "演示账号") -> dict[str, object]:
    return {
        "schema_version": 1,
        "id": "sample-rod",
        "title": "导体杆示例课件",
        "owner": owner,
        "status": "pending_review",
        "source_input_type": "image",
        "physics_summary": {
            "topic": "匀强磁场中的滑动导体杆",
            "parameters": {"B_T": 0.5, "L_m": 1.0, "v_m_s": 2.0, "R_ohm": 0.4},
            "magnetic_direction": "向里",
            "motion_direction": "向右",
            "current_direction": "d→c",
            "asks": ["求电动势"],
        },
        "generated_at": "2026-07-28T08:00:00+08:00",
        "path": "generator/staging/sample-rod/",
        "review": {"reviewer": "待老师确认", "reviewed_at": None, "physics_confirmed": False},
    }


class MetadataTests(unittest.TestCase):
    def test_owner_is_required_and_nonempty(self) -> None:
        with self.assertRaisesRegex(MetadataError, "owner"):
            validate_metadata(candidate_metadata(owner=""))

    def test_published_item_requires_confirmed_review(self) -> None:
        metadata = candidate_metadata()
        metadata["status"] = "published"
        with self.assertRaisesRegex(MetadataError, "物理确认"):
            validate_metadata(metadata)

    def test_promote_requires_explicit_physics_acceptance(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self._repository(Path(temp_dir))
            with self.assertRaisesRegex(MetadataError, "accept-physics"):
                LibraryManager(root).promote("sample-rod", "李老师", False)

    def test_promote_copies_candidate_and_updates_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self._repository(Path(temp_dir))
            published = LibraryManager(root).promote("sample-rod", "李老师", True)
            self.assertEqual(published["owner"], "演示账号")
            self.assertEqual(published["status"], "published")
            self.assertTrue(published["review"]["physics_confirmed"])
            self.assertTrue((root / "library/courseware/sample-rod/index.html").is_file())
            self.assertTrue((root / "generator/staging/sample-rod/index.html").is_file())
            catalog = validate_catalog(root / "library/catalog.json", root=root)
            self.assertEqual([item["id"] for item in catalog["items"]], ["sample-rod"])

    def _repository(self, root: Path) -> Path:
        (root / "library/courseware").mkdir(parents=True)
        (root / "generator/staging/sample-rod").mkdir(parents=True)
        (root / "generator/staging/sample-rod/index.html").write_text("<h1>sample</h1>", encoding="utf-8")
        (root / "generator/staging/sample-rod/metadata.json").write_text(
            json.dumps(candidate_metadata(), ensure_ascii=False), encoding="utf-8"
        )
        (root / "library/catalog.json").write_text(
            json.dumps({"schema_version": 1, "items": []}), encoding="utf-8"
        )
        return root


if __name__ == "__main__":
    unittest.main()
