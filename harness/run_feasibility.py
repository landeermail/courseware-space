#!/usr/bin/env python3
"""Run real Kimi harness probes and preserve non-overwritable evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "server"))

from harness.assertions import AssertionFailure  # noqa: E402
from harness.contracts import GeneratedArtifact, GeneratedModel, GeneratedView  # noqa: E402
from harness.pipeline import (  # noqa: E402
    DOMAIN_CONTRACTS,
    PROMPT_VERSION,
    TERMINAL_PROVIDER_KINDS,
    VIEW_SYSTEM_PROMPT,
    HarnessGenerationError,
)
from harness.domains.circular import circular_probe_inputs, validate_circular  # noqa: E402
from harness.domains.projectile import projectile_probe_inputs, validate_projectile  # noqa: E402
from harness.sandbox import execute_model  # noqa: E402
from kimi_client import DEFAULT_MODEL, KimiCodeClient  # noqa: E402
from server.harness_service import HarnessService  # noqa: E402


HERE = Path(__file__).resolve().parent
EVIDENCE = HERE / "evidence"


class HybridClient:
    def __init__(self) -> None:
        if "HARNESS_KIMI_MODEL" in os.environ:
            raise ValueError("HARNESS_KIMI_MODEL 已禁用；harness 模型由代码固定")
        self.provider = KimiCodeClient(model=DEFAULT_MODEL, max_retries=0)
        self.model = self.provider.model
        self._last_metadata: dict[str, Any] | None = None

    def _complete_phase(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        artifact_id: str,
        prompt_version: str,
        phase: str,
    ) -> str:
        cache_material = f"{self.model}|high|{prompt_version}|{artifact_id}|{phase}"
        cache_key = hashlib.sha256(cache_material.encode("utf-8")).hexdigest()
        self._last_metadata = None
        result = self.provider.complete_result(
            system_prompt,
            user_prompt,
            phase=phase,
            prompt_cache_key=cache_key,
            stream=True,
        )
        self._last_metadata = result.metadata
        return result.content

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        artifact_id: str,
        prompt_version: str,
    ) -> str:
        return self._complete_phase(
            system_prompt,
            user_prompt,
            artifact_id=artifact_id,
            prompt_version=prompt_version,
            phase="physics_model",
        )

    def complete_model(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        artifact_id: str,
        prompt_version: str,
    ) -> str:
        return self._complete_phase(
            system_prompt,
            user_prompt,
            artifact_id=artifact_id,
            prompt_version=prompt_version,
            phase="physics_model",
        )

    def complete_view(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        artifact_id: str,
        prompt_version: str,
    ) -> str:
        return self._complete_phase(
            system_prompt,
            user_prompt,
            artifact_id=artifact_id,
            prompt_version=prompt_version,
            phase="teaching_view",
        )

    def take_last_metadata(self) -> dict[str, Any] | None:
        metadata = self._last_metadata
        self._last_metadata = None
        return metadata


def load_cases(domain: str, fixture_set: str = "development") -> list[dict[str, Any]]:
    suffix = "" if fixture_set == "development" else f"-{fixture_set}"
    path = HERE / "fixtures" / f"{domain}{suffix}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_generation(
    domain: str,
    pilot: bool,
    run_name: str | None,
    fixture_set: str = "development",
) -> int:
    label = run_name or (f"{domain}-pilot" if pilot else domain)
    if not label.replace("-", "").isalnum() or len(label) > 80:
        print("run-name 只允许字母、数字、连字符且不超过 80 字符", file=sys.stderr)
        return 2
    output_root = EVIDENCE / "generated" / label
    result_path = output_root / "results.json"
    progress_path = output_root / "in-progress.json"
    if result_path.exists():
        print(f"拒绝重跑：结果已存在 {result_path.relative_to(ROOT)}", file=sys.stderr)
        return 2
    client = HybridClient()
    if not client.provider.configured:
        print("缺少 KIMI_API_KEY", file=sys.stderr)
        return 2
    all_cases = load_cases(domain, fixture_set)
    cases = all_cases[:1] if pilot else all_cases
    if progress_path.exists():
        progress = json.loads(progress_path.read_text(encoding="utf-8"))
        records = progress["records"]
    else:
        records: list[dict[str, Any]] = []
        progress = {
            "acceptance": f"harness-{label}-v1",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "model": client.model,
            "fixture_set": fixture_set,
            "records": records,
        }
        write_json(progress_path, progress)
    completed = {record["id"] for record in records}
    batch_status = "completed"
    for index, case in enumerate(cases, 1):
        if case["id"] in completed:
            print(f"[{index}/{len(cases)}] {case['id']}: preserved existing first attempt", flush=True)
            continue
        case_output = output_root / case["id"]
        if case_output.exists():
            raise RuntimeError(f"发现无结果记录的残留目录，拒绝覆盖：{case_output.relative_to(ROOT)}")
        service = HarnessService(client)
        token = service.confirm(domain, case["scenario"], True)
        try:
            result = service.generate(
                artifact_id=case["id"],
                domain=domain,
                question=case["question"],
                scenario=case["scenario"],
                confirmation_token=token,
                output_dir=case_output,
                max_attempts=3,
            )
            record = {"id": case["id"], "question": case["question"], "scenario": case["scenario"], **result.as_dict()}
            print(f"[{index}/{len(cases)}] {case['id']}: succeeded attempts={result.attempts}", flush=True)
        except Exception as error:
            error_kind = error.kind if isinstance(error, HarnessGenerationError) else "rejected"
            record = {
                "id": case["id"],
                "question": case["question"],
                "scenario": case["scenario"],
                "status": error_kind if error_kind in {"provider_unavailable", "output_limited"} else "rejected",
                "reason": str(error),
            }
            print(f"[{index}/{len(cases)}] {case['id']}: rejected {error}", flush=True)
        records.append(record)
        progress["records"] = records
        progress["updated_at"] = datetime.now(timezone.utc).isoformat()
        if record["status"] in {"provider_unavailable", "output_limited"}:
            batch_status = record["status"]
            progress["batch_status"] = batch_status
        write_json(progress_path, progress)
        if batch_status in {"provider_unavailable", "output_limited"}:
            print(f"{batch_status}: batch stopped to preserve quota and evidence", flush=True)
            break
    payload = {
        "acceptance": f"harness-{label}-v1",
        "ran_at": datetime.now(timezone.utc).isoformat(),
        "model": client.model,
        "fixture_set": fixture_set,
        "batch_status": batch_status,
        "planned_count": len(cases),
        "count": len(records),
        "successful": sum(record["status"] == "succeeded" for record in records),
        "records": records,
    }
    write_json(result_path, payload)
    return 0 if payload["successful"] == len(records) else 1


def final_artifact(output_dir: Path) -> GeneratedArtifact:
    payload = json.loads((output_dir / "source.json").read_text(encoding="utf-8"))
    return GeneratedArtifact(**payload)


def mutate_model(domain: str, code: str, fault: str) -> str:
    mutations = {
        "projectile": {
            "velocity_direction": "clone.states[1].vy_m_s *= -1;",
            "energy_conservation": "clone.states[2].mechanical_j += 100;",
            "range_critical": "clone.events.range_m *= 0.5;",
        },
        "circular": {
            "centripetal_direction": "clone.states[1].ax_m_s2 *= -1; clone.states[1].ay_m_s2 *= -1;",
            "energy_conservation": "clone.states[2].mechanical_j += 100;",
            "top_critical": "clone.events.critical_top_speed_m_s = 0;",
        },
    }
    injection = mutations[domain][fault]
    return (
        code
        + "\n;const __validatedBase=globalThis.coursewareModel;"
        + "globalThis.coursewareModel=Object.freeze({sample(input){"
        + "const clone=JSON.parse(JSON.stringify(__validatedBase.sample(input)));"
        + injection
        + "return clone;}});"
    )


def run_faults(domain: str, source_root: Path | None = None, run_name: str | None = None) -> int:
    source_root = source_root or EVIDENCE / "generated" / domain
    label = run_name or domain
    if not label.replace("-", "").isalnum() or len(label) > 80:
        print("run-name 只允许字母、数字、连字符且不超过 80 字符", file=sys.stderr)
        return 2
    result_path = EVIDENCE / "faults" / label / "results.json"
    if result_path.exists():
        print(f"拒绝重跑：结果已存在 {result_path.relative_to(ROOT)}", file=sys.stderr)
        return 2
    source_results = json.loads((source_root / "results.json").read_text(encoding="utf-8"))
    default_source_record = next(
        (record for record in source_results["records"] if record.get("status") == "succeeded"),
        None,
    )
    if default_source_record is None:
        raise RuntimeError("源证据没有成功生成的课件")
    faults = (
        ["velocity_direction", "energy_conservation", "range_critical"]
        if domain == "projectile"
        else ["centripetal_direction", "energy_conservation", "top_critical"]
    )
    records: list[dict[str, Any]] = []
    for fault in faults:
        source_record = default_source_record
        if domain == "circular" and fault == "top_critical":
            source_record = next(
                (
                    record
                    for record in source_results["records"]
                    if record.get("status") == "succeeded"
                    and record.get("scenario", {}).get("mode") == "vertical_string"
                ),
                None,
            )
            if source_record is None:
                raise RuntimeError("最高点临界故障需要成功的竖直圆周源课件")
        source = source_root / source_record["id"]
        artifact = final_artifact(source)
        scenario = source_record["scenario"]
        probes = projectile_probe_inputs(scenario) if domain == "projectile" else circular_probe_inputs(scenario)
        validator = validate_projectile if domain == "projectile" else validate_circular
        wrong = mutate_model(domain, artifact.model_js, fault)
        red_failed: list[str] = []
        try:
            output = execute_model(wrong, probes[0])
            axis = probes[0]["times_s"] if domain == "projectile" else probes[0]["angles_rad"]
            validator(probes[0]["scenario"], output, axis).require()
        except AssertionFailure as error:
            red_failed = [check.name for check in error.report.checks if not check.passed]
        if not red_failed:
            raise RuntimeError(f"故障 {fault} 未被断言拦截")
        green_reports = []
        for probe in probes:
            output = execute_model(artifact.model_js, probe)
            axis = probe["times_s"] if domain == "projectile" else probe["angles_rad"]
            report = validator(probe["scenario"], output, axis)
            report.require()
            green_reports.append(report.as_dict())
        record = {
            "fault": fault,
            "source_artifact": str(source.relative_to(ROOT)),
            "source_mode": scenario["mode"],
            "red_status": "blocked",
            "red_failed": red_failed,
            "green_status": "passed",
            "green_probe_count": len(green_reports),
        }
        records.append(record)
        print(f"{fault}: RED blocked ({red_failed[0]}) -> GREEN {len(green_reports)} probes", flush=True)
    write_json(
        result_path,
        {
            "acceptance": f"harness-{domain}-faults-v1",
            "ran_at": datetime.now(timezone.utc).isoformat(),
            "source_artifacts": sorted({record["source_artifact"] for record in records}),
            "records": records,
        },
    )
    return 0


def run_revalidate(domain: str, source: Path, run_name: str) -> int:
    destination = EVIDENCE / "generated" / run_name / source.name
    result_path = destination.parent / "results.json"
    if result_path.exists() or destination.exists():
        print(f"拒绝覆盖 revalidation 证据：{destination.relative_to(ROOT)}", file=sys.stderr)
        return 2
    source_root = source.parent
    source_results = json.loads((source_root / "results.json").read_text(encoding="utf-8"))
    record = next(item for item in source_results["records"] if item["id"] == source.name)
    scenario = record["scenario"]
    model: GeneratedModel | None = None
    model_source = ""
    for path in sorted((source / "model-attempts").glob("*.json")):
        attempt = json.loads(path.read_text(encoding="utf-8"))
        if attempt.get("status") == "passed":
            model = GeneratedModel.parse(attempt["raw"], domain)
            model_source = str(path.relative_to(ROOT))
            break
    if model is None:
        raise RuntimeError("源证据没有已通过的物理模型")
    view: GeneratedView | None = None
    view_source = ""
    for path in sorted((source / "view-attempts").glob("*.json")):
        attempt = json.loads(path.read_text(encoding="utf-8"))
        if not attempt.get("raw"):
            continue
        try:
            view = GeneratedView.parse(attempt["raw"])
        except Exception:
            continue
        view_source = str(path.relative_to(ROOT))
        break
    if view is None:
        raise RuntimeError("源证据没有可由当前契约接纳的教学视图")
    probes = projectile_probe_inputs(scenario) if domain == "projectile" else circular_probe_inputs(scenario)
    validator = validate_projectile if domain == "projectile" else validate_circular
    reports = []
    for index, probe in enumerate(probes):
        axis = probe["times_s"] if domain == "projectile" else probe["angles_rad"]
        assertion_report = validator(probe["scenario"], execute_model(model.model_js, probe), axis)
        assertion_report.require()
        reports.append({"probe": index, **assertion_report.as_dict()})
    artifact = GeneratedArtifact(model.title, model.domain, view.teaching_intent, model.model_js, view.html)
    primitive_js = (HERE / "primitives.js").read_text(encoding="utf-8")
    destination.mkdir(parents=True)
    (destination / "index.html").write_text(artifact.render(primitive_js, probes[0]), encoding="utf-8")
    (destination / "model.js").write_text(model.model_js + "\n", encoding="utf-8")
    write_json(destination / "source.json", artifact.as_dict())
    write_json(destination / "assertion-report.json", {"passed": True, "reports": reports})
    write_json(
        destination / "metadata.json",
        {
            "id": source.name,
            "domain": domain,
            "status": "succeeded",
            "revalidated": True,
            "source_model_attempt": model_source,
            "source_view_attempt": view_source,
            "probe_count": len(reports),
            "output_path": str((destination / "index.html").relative_to(ROOT)),
            "teaching_intent": view.teaching_intent,
            "view_normalizations": list(view.normalizations),
        },
    )
    write_json(
        result_path,
        {
            "acceptance": f"harness-{run_name}-revalidated-v1",
            "ran_at": datetime.now(timezone.utc).isoformat(),
            "successful": 1,
            "records": [json.loads((destination / "metadata.json").read_text(encoding="utf-8"))],
        },
    )
    print(f"revalidated: {destination.relative_to(ROOT)} probes={len(reports)}")
    return 0


def run_view_repair(
    domain: str,
    source_root: Path,
    findings_path: Path,
    run_name: str,
) -> int:
    if not run_name.replace("-", "").isalnum() or len(run_name) > 80:
        print("run-name 只允许字母、数字、连字符且不超过 80 字符", file=sys.stderr)
        return 2
    output_root = EVIDENCE / "generated" / run_name
    result_path = output_root / "results.json"
    if output_root.exists():
        print(f"拒绝覆盖 repair 证据：{output_root.relative_to(ROOT)}", file=sys.stderr)
        return 2
    client = HybridClient()
    if not client.provider.configured:
        print("缺少 KIMI_API_KEY", file=sys.stderr)
        return 2
    source_results = json.loads((source_root / "results.json").read_text(encoding="utf-8"))
    findings_payload = json.loads(findings_path.read_text(encoding="utf-8"))
    findings = {record["id"]: record for record in findings_payload["records"]}
    primitive_js = (HERE / "primitives.js").read_text(encoding="utf-8")
    records: list[dict[str, Any]] = []
    batch_status = "completed"
    output_root.mkdir(parents=True)

    for index, source_record in enumerate(source_results["records"], 1):
        artifact_id = source_record["id"]
        source_dir = source_root / artifact_id
        source_payload = json.loads((source_dir / "source.json").read_text(encoding="utf-8"))
        model = GeneratedModel(source_payload["title"], source_payload["domain"], source_payload["model_js"])
        scenario = source_record["scenario"]
        question = source_record["question"]
        probes = projectile_probe_inputs(scenario) if domain == "projectile" else circular_probe_inputs(scenario)
        validator = validate_projectile if domain == "projectile" else validate_circular
        reports: list[dict[str, Any]] = []
        for probe_index, probe in enumerate(probes):
            axis = probe["times_s"] if domain == "projectile" else probe["angles_rad"]
            assertion_report = validator(probe["scenario"], execute_model(model.model_js, probe), axis)
            assertion_report.require()
            reports.append({"probe": probe_index, **assertion_report.as_dict()})

        finding = findings.get(artifact_id, {"status": "rejected", "reason": "缺少浏览器验收记录"})
        view: GeneratedView | None = None
        original_metadata = json.loads((source_dir / "metadata.json").read_text(encoding="utf-8"))
        original_view_attempts = int(original_metadata.get("view_attempts", 1))
        needs_repair = finding.get("status") != "passed_initial_state"
        if not needs_repair:
            try:
                view = GeneratedView.parse(
                    json.dumps(
                        {"teaching_intent": source_payload["teaching_intent"], "html": source_payload["html"]},
                        ensure_ascii=False,
                    )
                )
            except Exception as error:
                needs_repair = True
                finding = {"status": "rejected", "reason": f"当前契约复验失败：{error}"}

        output_dir = output_root / artifact_id
        attempt_dir = output_dir / "view-attempts"
        repair_attempts = 0
        failure_messages: list[str] = []
        if needs_repair:
            remaining_attempts = max(0, 3 - original_view_attempts)
            attempt_dir.mkdir(parents=True)
            for attempt in range(1, remaining_attempts + 1):
                repair_attempts = attempt
                prompt = (
                    f"题目：{question.strip()}\n"
                    f"老师已确认场景 JSON：{json.dumps(scenario, ensure_ascii=False, sort_keys=True)}\n"
                    f"标题：{model.title}\n"
                    f"物理模型输入输出契约：\n{DOMAIN_CONTRACTS[domain]}\n"
                    f"上一版浏览器验收失败：{finding['reason']}\n"
                    "保留自由教学设计，但必须修正浏览器失败，并重新完整输出教学视图。"
                )
                if failure_messages:
                    prompt += f"\n本轮契约拒绝原因：\n{failure_messages[-1]}"
                attempt_record: dict[str, Any] = {
                    "attempt": attempt,
                    "prompt_version": PROMPT_VERSION,
                    "ran_at": datetime.now(timezone.utc).isoformat(),
                    "raw": "",
                }
                try:
                    raw = client.complete_view(
                        VIEW_SYSTEM_PROMPT,
                        prompt,
                        artifact_id=f"{artifact_id}-browser-repair",
                        prompt_version=PROMPT_VERSION,
                    )
                    attempt_record["raw"] = raw
                    provider_metadata = client.take_last_metadata()
                    if provider_metadata is not None:
                        attempt_record["provider"] = provider_metadata
                    view = GeneratedView.parse(raw)
                    attempt_record["status"] = "passed"
                    write_json(attempt_dir / f"{attempt:02d}.json", attempt_record)
                    break
                except RuntimeError as error:
                    failure_kind = getattr(error, "kind", "provider")
                    message = f"视图传输失败：{error}"
                    failure_messages.append(message)
                    attempt_record.update({"status": "provider_failed", "failure_kind": failure_kind, "failure": message})
                    error_metadata = getattr(error, "metadata", None)
                    if isinstance(error_metadata, dict):
                        attempt_record["provider"] = error_metadata
                    write_json(attempt_dir / f"{attempt:02d}.json", attempt_record)
                    if failure_kind in TERMINAL_PROVIDER_KINDS:
                        batch_status = "provider_unavailable" if failure_kind != "length_limit" else "output_limited"
                        break
                except Exception as error:
                    message = str(error)
                    failure_messages.append(message)
                    attempt_record.update({"status": "rejected", "failure": message})
                    write_json(attempt_dir / f"{attempt:02d}.json", attempt_record)

        if view is None:
            status = batch_status if batch_status != "completed" else "rejected"
            record = {
                "id": artifact_id,
                "question": question,
                "scenario": scenario,
                "status": status,
                "reason": failure_messages[-1] if failure_messages else "浏览器失败后的视图重试额度已用尽",
                "source_artifact": str(source_dir.relative_to(ROOT)),
                "original_view_attempts": original_view_attempts,
                "repair_attempts": repair_attempts,
            }
            records.append(record)
            print(f"[{index}/{len(source_results['records'])}] {artifact_id}: {status}", flush=True)
            if batch_status != "completed":
                break
            continue

        output_dir.mkdir(parents=True, exist_ok=True)
        artifact = GeneratedArtifact(model.title, model.domain, view.teaching_intent, model.model_js, view.html)
        (output_dir / "index.html").write_text(artifact.render(primitive_js, probes[0]), encoding="utf-8")
        (output_dir / "model.js").write_text(model.model_js + "\n", encoding="utf-8")
        write_json(output_dir / "source.json", artifact.as_dict())
        write_json(output_dir / "assertion-report.json", {"passed": True, "reports": reports})
        metadata = {
            "id": artifact_id,
            "domain": domain,
            "status": "succeeded",
            "attempts": int(original_metadata.get("model_attempts", 1)) + original_view_attempts + repair_attempts,
            "model_attempts": int(original_metadata.get("model_attempts", 1)),
            "view_attempts": original_view_attempts + repair_attempts,
            "repair_attempts": repair_attempts,
            "output_path": str((output_dir / "index.html").relative_to(ROOT)),
            "teaching_intent": view.teaching_intent,
            "source_artifact": str(source_dir.relative_to(ROOT)),
            "browser_finding": finding,
        }
        write_json(output_dir / "metadata.json", metadata)
        records.append({"id": artifact_id, "question": question, "scenario": scenario, **metadata})
        print(f"[{index}/{len(source_results['records'])}] {artifact_id}: succeeded repair_attempts={repair_attempts}", flush=True)

    write_json(
        result_path,
        {
            "acceptance": f"harness-{run_name}-browser-repair-v1",
            "ran_at": datetime.now(timezone.utc).isoformat(),
            "model": client.model,
            "batch_status": batch_status,
            "planned_count": len(source_results["records"]),
            "count": len(records),
            "successful": sum(record["status"] == "succeeded" for record in records),
            "source_run": str(source_root.relative_to(ROOT)),
            "browser_findings": str(findings_path.relative_to(ROOT)),
            "records": records,
        },
    )
    return 0 if len(records) == len(source_results["records"]) and all(record["status"] == "succeeded" for record in records) else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    generate = subparsers.add_parser("generate")
    generate.add_argument("domain", choices=("projectile", "circular"))
    generate.add_argument("--pilot", action="store_true")
    generate.add_argument("--run-name")
    generate.add_argument("--fixture-set", choices=("development", "holdout"), default="development")
    faults = subparsers.add_parser("faults")
    faults.add_argument("domain", choices=("projectile", "circular"))
    faults.add_argument("--source-root", type=Path)
    faults.add_argument("--run-name")
    revalidate = subparsers.add_parser("revalidate")
    revalidate.add_argument("domain", choices=("projectile", "circular"))
    revalidate.add_argument("--source", required=True, type=Path)
    revalidate.add_argument("--run-name", required=True)
    repair = subparsers.add_parser("repair-views")
    repair.add_argument("domain", choices=("projectile", "circular"))
    repair.add_argument("--source-root", required=True, type=Path)
    repair.add_argument("--findings", required=True, type=Path)
    repair.add_argument("--run-name", required=True)
    args = parser.parse_args()
    if args.command == "generate":
        if not os.environ.get("KIMI_API_KEY"):
            print("缺少 KIMI_API_KEY", file=sys.stderr)
            return 2
        return run_generation(args.domain, args.pilot, args.run_name, args.fixture_set)
    if args.command == "faults":
        return run_faults(
            args.domain,
            args.source_root.resolve() if args.source_root else None,
            args.run_name,
        )
    if args.command == "repair-views":
        if not os.environ.get("KIMI_API_KEY"):
            print("缺少 KIMI_API_KEY", file=sys.stderr)
            return 2
        return run_view_repair(
            args.domain,
            args.source_root.resolve(),
            args.findings.resolve(),
            args.run_name,
        )
    return run_revalidate(args.domain, args.source.resolve(), args.run_name)


if __name__ == "__main__":
    raise SystemExit(main())
