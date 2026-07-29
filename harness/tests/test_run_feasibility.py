from __future__ import annotations

import json
import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from harness import run_feasibility
from harness.pipeline import HarnessGenerationError


class FakeHybridClient:
    def __init__(self) -> None:
        self.model = "fake-kimi"
        self.provider = type("Provider", (), {"configured": True})()


class QuotaLimitedService:
    calls = 0

    def __init__(self, client: object) -> None:
        pass

    def confirm(self, domain: str, scenario: dict[str, object], teacher_confirmed: bool) -> str:
        return "confirmed"

    def generate(self, **kwargs: object) -> object:
        type(self).calls += 1
        raise HarnessGenerationError("quota", kind="provider_unavailable")


class FeasibilityBatchTests(unittest.TestCase):
    def test_holdout_cases_are_separate_complete_sets(self) -> None:
        for domain in ("projectile", "circular"):
            development = {case["id"] for case in run_feasibility.load_cases(domain)}
            holdout = run_feasibility.load_cases(domain, "holdout")
            self.assertEqual(len(holdout), 5)
            self.assertTrue(development.isdisjoint({case["id"] for case in holdout}))

    def test_harness_rejects_model_environment_override(self) -> None:
        with patch.dict(os.environ, {"HARNESS_KIMI_MODEL": "kimi-for-coding-highspeed"}):
            with self.assertRaisesRegex(ValueError, "已禁用"):
                run_feasibility.HybridClient()

    def test_harness_uses_fixed_k3_256k_model(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("HARNESS_KIMI_MODEL", None)
            client = run_feasibility.HybridClient()
        self.assertEqual(client.model, "k3-256k")

    def test_cache_key_is_stable_per_task_phase_and_separated_across_phases(self) -> None:
        calls: list[dict[str, object]] = []

        class FakeProvider:
            configured = True

            def complete_result(self, *args: object, **kwargs: object) -> object:
                calls.append(dict(kwargs))
                return type("Result", (), {"content": "{}", "metadata": {"usage": {"total_tokens": 1}}})()

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("HARNESS_KIMI_MODEL", None)
            client = run_feasibility.HybridClient()
        client.provider = FakeProvider()
        client.complete_model("system", "user", artifact_id="case-1", prompt_version="v1")
        client.complete_model("system", "retry", artifact_id="case-1", prompt_version="v1")
        client.complete_view("system", "user", artifact_id="case-1", prompt_version="v1")
        self.assertEqual(calls[0]["prompt_cache_key"], calls[1]["prompt_cache_key"])
        self.assertNotEqual(calls[0]["prompt_cache_key"], calls[2]["prompt_cache_key"])
        self.assertEqual(calls[0]["phase"], "physics_model")
        self.assertEqual(calls[2]["phase"], "teaching_view")
        self.assertTrue(all(call["stream"] is True for call in calls))
        self.assertEqual(client.take_last_metadata(), {"usage": {"total_tokens": 1}})

    def test_terminal_provider_error_stops_batch_after_first_case(self) -> None:
        QuotaLimitedService.calls = 0
        with tempfile.TemporaryDirectory() as directory, patch.object(
            run_feasibility, "EVIDENCE", Path(directory)
        ), patch.object(run_feasibility, "HybridClient", FakeHybridClient), patch.object(
            run_feasibility, "HarnessService", QuotaLimitedService
        ):
            with redirect_stdout(io.StringIO()):
                exit_code = run_feasibility.run_generation("projectile", False, "quota-stop-test")
            result = json.loads((Path(directory) / "generated" / "quota-stop-test" / "results.json").read_text())
        self.assertEqual(exit_code, 1)
        self.assertEqual(QuotaLimitedService.calls, 1)
        self.assertEqual(result["planned_count"], 5)
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["batch_status"], "provider_unavailable")
