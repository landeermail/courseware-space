from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research.generation.harness import audit_acceptance


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


class EvidenceAuditTests(unittest.TestCase):
    def test_reference_only_results_cannot_count_as_generation(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch.object(audit_acceptance, "EVIDENCE", Path(directory)):
            write_json(
                Path(directory) / "generated" / "reference" / "results.json",
                {"classification": "reference_only_not_model_generated", "generated_acceptance_credit": 0},
            )
            with self.assertRaisesRegex(audit_acceptance.EvidenceAuditError, "reference-only"):
                audit_acceptance.audit_domain("circular", "reference", "unused", "unused")

    def test_five_complete_artifacts_and_three_faults_pass(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch.object(audit_acceptance, "EVIDENCE", Path(directory)):
            root = Path(directory) / "generated" / "complete"
            records = []
            browser_records = []
            for index in range(5):
                artifact_id = f"case-{index}"
                artifact = root / artifact_id
                artifact.mkdir(parents=True)
                for filename in ("index.html", "model.js", "source.json", "metadata.json"):
                    (artifact / filename).write_text("{}", encoding="utf-8")
                write_json(artifact / "assertion-report.json", {"passed": True, "reports": [{"passed": True}] * 5})
                records.append({"id": artifact_id, "status": "succeeded"})
                browser_records.append(
                    {
                        "id": artifact_id,
                        "initial_scenario": "matched",
                        "initial_time_s": 0,
                        "initial_playing": False,
                        "pause_stable": True,
                        "replay_reset_to_s": 0,
                        "parameter_resampled": True,
                        "runtime_error": None,
                        "desktop_overflow_x": False,
                        "ipad_overflow_x": False,
                        "min_target_height_px": 44,
                        "interactive_overlaps": 0,
                    }
                )
            write_json(root / "results.json", {"records": records})
            write_json(
                Path(directory) / "browser" / "complete" / "results.json",
                {"records": browser_records},
            )
            write_json(
                Path(directory) / "faults" / "complete" / "results.json",
                {"records": [{"red_status": "blocked", "green_status": "passed"}] * 3},
            )
            report = audit_acceptance.audit_domain("projectile", "complete", "complete", "complete")
            self.assertEqual(report["generated"], 5)
            self.assertEqual(report["faults_red_green"], 3)
