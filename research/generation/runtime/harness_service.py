"""Server-owned confirmation and generation entry point for the feasibility harness."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPOSITORY_ROOT))

from research.generation.harness.confirmation import TeacherConfirmationGate  # noqa: E402
from research.generation.harness.domains.circular import normalize_circular  # noqa: E402
from research.generation.harness.domains.projectile import normalize_projectile  # noqa: E402
from research.generation.harness.pipeline import HarnessGenerationResult, HarnessPipeline  # noqa: E402


class HarnessService:
    def __init__(self, client: Any) -> None:
        self.gate = TeacherConfirmationGate()
        self.pipeline = HarnessPipeline(client, self.gate)

    def confirm(self, domain: str, scenario: dict[str, Any], teacher_confirmed: bool) -> str:
        normalized = self._normalize(domain, scenario)
        return self.gate.confirm(domain, normalized, teacher_confirmed)

    @staticmethod
    def _normalize(domain: str, scenario: dict[str, Any]) -> dict[str, Any]:
        if domain == "projectile":
            return normalize_projectile(scenario)
        if domain == "circular":
            return normalize_circular(scenario)
        raise ValueError("harness 只接受 projectile 或 circular")

    def generate(
        self,
        *,
        artifact_id: str,
        domain: str,
        question: str,
        scenario: dict[str, Any],
        confirmation_token: str,
        output_dir: Path,
        max_attempts: int = 3,
    ) -> HarnessGenerationResult:
        normalized = self._normalize(domain, scenario)
        return self.pipeline.generate(
            artifact_id=artifact_id,
            domain=domain,
            question=question,
            scenario=normalized,
            confirmation_token=confirmation_token,
            output_dir=output_dir,
            max_attempts=max_attempts,
        )
