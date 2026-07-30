#!/usr/bin/env python3
"""Prove the circular harness accepts a reference model without counting it as generation."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from harness.assertions import AssertionFailure  # noqa: E402
from harness.domains.circular import circular_probe_inputs, validate_circular  # noqa: E402
from harness.run_feasibility import mutate_model  # noqa: E402
from harness.sandbox import execute_model  # noqa: E402


HERE = Path(__file__).resolve().parent
RESULT = HERE / "evidence" / "reference" / "circular-sandbox-v2" / "results.json"


def main() -> int:
    if RESULT.exists():
        print(f"拒绝覆盖参考证据：{RESULT.relative_to(ROOT)}", file=sys.stderr)
        return 2
    cases: list[dict[str, Any]] = json.loads((HERE / "fixtures" / "circular.json").read_text(encoding="utf-8"))
    model_js = (HERE / "reference" / "circular_model.js").read_text(encoding="utf-8")
    case_records: list[dict[str, Any]] = []
    for case in cases:
        probes = circular_probe_inputs(case["scenario"])
        reports = []
        for probe in probes:
            output = execute_model(model_js, probe)
            report = validate_circular(probe["scenario"], output, probe["angles_rad"])
            report.require()
            reports.append({"passed": report.passed, "check_count": len(report.checks)})
        case_records.append({"id": case["id"], "status": "passed", "probe_count": len(reports), "reports": reports})
        print(f"{case['id']}: reference GREEN {len(reports)} probes", flush=True)

    fault_case = next(case for case in cases if case["id"] == "circular-vertical-critical")
    fault_probe = circular_probe_inputs(fault_case["scenario"])[0]
    fault_records = []
    for fault in ("centripetal_direction", "energy_conservation", "top_critical"):
        failed: list[str] = []
        try:
            output = execute_model(mutate_model("circular", model_js, fault), fault_probe)
            validate_circular(fault_probe["scenario"], output, fault_probe["angles_rad"]).require()
        except AssertionFailure as error:
            failed = [check.name for check in error.report.checks if not check.passed]
        if not failed:
            raise RuntimeError(f"参考故障 {fault} 未被 harness 拦截")
        fault_records.append({"fault": fault, "red_status": "blocked", "red_failed": failed})
        print(f"{fault}: reference RED blocked ({failed[0]})", flush=True)

    RESULT.parent.mkdir(parents=True, exist_ok=True)
    RESULT.write_text(
        json.dumps(
            {
                "acceptance": "harness-circular-reference-only-v1",
                "ran_at": datetime.now(timezone.utc).isoformat(),
                "classification": "reference_only_not_model_generated",
                "generated_acceptance_credit": 0,
                "cases": case_records,
                "faults": fault_records,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print("reference summary: cases 5/5, injected faults 3/3 blocked, generated credit 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
