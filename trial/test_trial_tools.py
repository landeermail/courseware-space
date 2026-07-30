from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

from build_private_materials import MaterialError, build


HERE = Path(__file__).resolve().parent


def manifest(content: str = "<p>仅含题目。</p>") -> dict[str, object]:
    return {
        "schema_version": 1,
        "source_label": "内部测试来源",
        "questions": [
            {
                "id": question_id,
                "number": f"第 {index} 题",
                "title": f"测试题 {index}",
                "content_html": content,
                "image_member": "word/media/diagram.png",
                "image_alt": "测试图",
            }
            for index, question_id in enumerate(
                ("q01-test-one", "q02-test-two", "q03-test-three"), start=1
            )
        ],
    }


class PrivateMaterialBuilderTests(unittest.TestCase):
    def make_fixture(self, root: Path, payload: dict[str, object]) -> tuple[Path, Path]:
        source = root / "source.docx"
        with ZipFile(source, "w") as archive:
            archive.writestr("word/media/diagram.png", b"png fixture")
        manifest_path = root / "questions.json"
        manifest_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return source, manifest_path

    def test_builds_three_pages_inside_private_root(self) -> None:
        with tempfile.TemporaryDirectory(dir=HERE / "private") as directory:
            root = Path(directory)
            source, manifest_path = self.make_fixture(root, manifest())

            pages = build(source, manifest_path, root / "output")

            self.assertEqual(len(pages), 3)
            for page in pages:
                self.assertTrue(page.is_file())
                self.assertTrue((page.parent / "diagram.png").is_file())
                self.assertNotIn("{{", page.read_text(encoding="utf-8"))

    def test_rejects_output_outside_private_root(self) -> None:
        with tempfile.TemporaryDirectory(dir=HERE / "private") as directory:
            root = Path(directory)
            source, manifest_path = self.make_fixture(root, manifest())
            with tempfile.TemporaryDirectory() as public_directory:
                with self.assertRaisesRegex(MaterialError, "trial/private"):
                    build(source, manifest_path, Path(public_directory))

    def test_rejects_answer_leakage(self) -> None:
        with tempfile.TemporaryDirectory(dir=HERE / "private") as directory:
            root = Path(directory)
            source, manifest_path = self.make_fixture(root, manifest("<p>【答案】A</p>"))

            with self.assertRaisesRegex(MaterialError, "答案或解析"):
                build(source, manifest_path, root / "output")


if __name__ == "__main__":
    unittest.main()
