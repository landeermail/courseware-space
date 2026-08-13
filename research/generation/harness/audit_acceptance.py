#!/usr/bin/env python3
"""Fail closed unless one evidence run satisfies the task-book domain acceptance."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
EVIDENCE = ROOT / "harness" / "evidence"


class EvidenceAuditError(ValueError):
    pass


def _json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise EvidenceAuditError(f"缺少证据文件：{path.relative_to(ROOT)}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise EvidenceAuditError(f"证据必须是 JSON 对象：{path.relative_to(ROOT)}")
    return payload


def _artifact_path(generated_root: Path, record: dict[str, Any]) -> Path:
    declared = record.get("artifact_path")
    artifact = ROOT / declared if isinstance(declared, str) else generated_root / str(record.get("id", ""))
    resolved = artifact.resolve()
    evidence_root = (EVIDENCE / "generated").resolve()
    if resolved != evidence_root and evidence_root not in resolved.parents:
        raise EvidenceAuditError("生成物引用必须位于 research/generation/harness/evidence/generated")
    return resolved


def audit_domain(domain: str, generated_run: str, fault_run: str, browser_run: str) -> dict[str, Any]:
    generated_root = EVIDENCE / "generated" / generated_run
    results = _json(generated_root / "results.json")
    if results.get("classification") == "reference_only_not_model_generated" or results.get("generated_acceptance_credit") == 0:
        raise EvidenceAuditError(f"{domain} 使用了 reference-only 证据，不能计入生成验收")
    records = results.get("records")
    if not isinstance(records, list) or len(records) != 5:
        raise EvidenceAuditError(f"{domain} 生成记录必须恰好 5 条，当前 {len(records) if isinstance(records, list) else 0}/5")
    successful = [record for record in records if isinstance(record, dict) and record.get("status") == "succeeded"]
    if len(successful) != 5:
        raise EvidenceAuditError(f"{domain} 成功生成必须 5/5，当前 {len(successful)}/5")

    browser_payload = _json(EVIDENCE / "browser" / browser_run / "results.json")
    browser_records = browser_payload.get("accepted_records", browser_payload.get("records"))
    if not isinstance(browser_records, list):
        raise EvidenceAuditError(f"{domain} 浏览器证据缺少记录")
    browser_by_id = {
        record.get("id"): record for record in browser_records if isinstance(record, dict) and isinstance(record.get("id"), str)
    }
    if set(browser_by_id) != {record.get("id") for record in successful}:
        raise EvidenceAuditError(f"{domain} 浏览器通过记录与 5 个生成物不一致")

    artifacts = []
    for record in successful:
        artifact_id = record.get("id")
        if not isinstance(artifact_id, str) or not artifact_id:
            raise EvidenceAuditError(f"{domain} 生成记录缺少 id")
        artifact = _artifact_path(generated_root, record)
        for filename in ("index.html", "model.js", "source.json", "metadata.json"):
            if not (artifact / filename).is_file():
                raise EvidenceAuditError(f"{artifact_id} 缺少 {filename}")
        assertions = _json(artifact / "assertion-report.json")
        reports = assertions.get("reports")
        if assertions.get("passed") is not True or not isinstance(reports, list) or len(reports) < 5:
            raise EvidenceAuditError(f"{artifact_id} 断言报告未证明至少 5 组探针全绿")
        if any(not isinstance(report, dict) or report.get("passed") is not True for report in reports):
            raise EvidenceAuditError(f"{artifact_id} 存在未通过的物理探针")
        browser = browser_by_id[artifact_id]
        checks = {
            "initial_scenario": browser.get("initial_scenario") == "matched",
            "initial_time": browser.get("initial_time_s") == 0,
            "initial_paused": browser.get("initial_playing") is False,
            "pause": browser.get("pause_stable") is True,
            "replay": browser.get("replay_reset_to_s") == 0,
            "parameter": browser.get("parameter_resampled") is True,
            "runtime": browser.get("runtime_error") is None,
            "desktop_width": browser.get("desktop_overflow_x") is False,
            "ipad_width": browser.get("ipad_overflow_x") is False,
            "touch": browser.get("ipad_min_target_height_px", browser.get("min_target_height_px", 0)) >= 44,
            "overlap": browser.get("ipad_interactive_overlaps", browser.get("interactive_overlaps", -1)) == 0,
        }
        failed = [name for name, passed in checks.items() if not passed]
        if failed:
            raise EvidenceAuditError(f"{artifact_id} 浏览器验收失败：{', '.join(failed)}")
        artifacts.append({"id": artifact_id, "probe_count": len(reports), "browser_status": "passed"})

    fault_payload = _json(EVIDENCE / "faults" / fault_run / "results.json")
    faults = fault_payload.get("records")
    if not isinstance(faults, list) or len(faults) < 3:
        raise EvidenceAuditError(f"{domain} 至少需要 3 类故障红→绿，当前 {len(faults) if isinstance(faults, list) else 0}/3")
    for fault in faults:
        if fault.get("red_status") != "blocked" or fault.get("green_status") != "passed":
            raise EvidenceAuditError(f"{domain} 故障证据不是完整红→绿")

    return {"domain": domain, "generated": 5, "artifacts": artifacts, "faults_red_green": len(faults)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--projectile-run", required=True)
    parser.add_argument("--projectile-faults", required=True)
    parser.add_argument("--projectile-browser", required=True)
    parser.add_argument("--circular-run", required=True)
    parser.add_argument("--circular-faults", required=True)
    parser.add_argument("--circular-browser", required=True)
    args = parser.parse_args()
    try:
        reports = [
            audit_domain("projectile", args.projectile_run, args.projectile_faults, args.projectile_browser),
            audit_domain("circular", args.circular_run, args.circular_faults, args.circular_browser),
        ]
    except (EvidenceAuditError, json.JSONDecodeError) as error:
        print(f"acceptance audit: FAILED - {error}")
        return 1
    print(json.dumps({"status": "passed", "domains": reports}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
