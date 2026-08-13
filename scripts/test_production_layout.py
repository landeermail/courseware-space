from __future__ import annotations

from pathlib import Path
import subprocess
import unittest


REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
PRODUCTION_ROOT = REPOSITORY_ROOT / "production" / "courseware"
SOURCE_IMAGE_SHA256 = {
    "q01-vertical-circle": "9360684fb145644361f9820d7e239e3ff2629f1919f112508d49b05a47544618",
    "q07-glass-rod-tir": "589ce078908d72efaee5f9ee031e3efc11a449ddf2be39ba7d44d68602979ae1",
}


def record_fields(path: Path) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            break
        if line.startswith("- ") and ":" in line:
            key, value = line[2:].split(":", 1)
            fields[key] = value.strip()
    return fields


class ProductionLayoutTests(unittest.TestCase):
    def test_each_record_uses_the_production_module_paths(self) -> None:
        records = sorted(PRODUCTION_ROOT.glob("*/record.md"))
        self.assertGreaterEqual(len(records), 2)

        for record in records:
            with self.subTest(record=record.parent.name):
                courseware_id = record.parent.name
                fields = record_fields(record)
                expected_root = f"production/courseware/{courseware_id}"
                self.assertEqual(fields["courseware_id"], courseware_id)
                self.assertEqual(
                    fields["question_packet_path"], f"{expected_root}/input/"
                )
                self.assertEqual(
                    fields["candidate_path"], f"{expected_root}/work/candidate/"
                )
                self.assertEqual(
                    fields["evidence_path"], f"{expected_root}/work/evidence/"
                )
                self.assertNotIn("trial/private/", record.read_text(encoding="utf-8"))

    def test_versioned_inputs_and_release_references_exist(self) -> None:
        for record in sorted(PRODUCTION_ROOT.glob("*/record.md")):
            with self.subTest(record=record.parent.name):
                fields = record_fields(record)
                input_root = REPOSITORY_ROOT / fields["question_packet_path"]
                self.assertTrue((input_root / "question.md").is_file())
                if record.parent.name in SOURCE_IMAGE_SHA256:
                    import hashlib

                    source = input_root / "source.png"
                    self.assertTrue(source.is_file())
                    self.assertEqual(
                        hashlib.sha256(source.read_bytes()).hexdigest(),
                        SOURCE_IMAGE_SHA256[record.parent.name],
                    )

                release_root = REPOSITORY_ROOT / fields["release_root"]
                self.assertTrue(release_root.is_dir())

                manifest_ref = fields["artifact_manifest_ref"].split("#", 1)[0]
                if manifest_ref != "none":
                    self.assertTrue((REPOSITORY_ROOT / manifest_ref).is_file())

    def test_mutable_workspaces_are_ignored_and_untracked(self) -> None:
        ignore_rules = (REPOSITORY_ROOT / "production/.gitignore").read_text(
            encoding="utf-8"
        ).splitlines()
        self.assertIn("courseware/*/work/", ignore_rules)

        if (REPOSITORY_ROOT / ".git").exists():
            tracked = subprocess.run(
                ["git", "ls-files", "production/courseware"],
                cwd=REPOSITORY_ROOT,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.splitlines()
            self.assertFalse([path for path in tracked if "/work/" in path])

        for courseware_root in sorted(PRODUCTION_ROOT.iterdir()):
            if not courseware_root.is_dir():
                continue
            relative = courseware_root.relative_to(REPOSITORY_ROOT)
            for workspace in ("work/candidate/example", "work/evidence/example"):
                if (REPOSITORY_ROOT / ".git").exists():
                    result = subprocess.run(
                        ["git", "check-ignore", "-q", str(relative / workspace)],
                        cwd=REPOSITORY_ROOT,
                        check=False,
                    )
                    self.assertEqual(result.returncode, 0, str(relative / workspace))
                else:
                    self.assertFalse((REPOSITORY_ROOT / relative / workspace).exists())


if __name__ == "__main__":
    unittest.main()
