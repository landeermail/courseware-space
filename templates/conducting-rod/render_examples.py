#!/usr/bin/env python3
"""Render deterministic example pages from the locked conducting-rod template."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

from physics import assert_physics, derive_physics, normalize_config


ROOT = Path(__file__).resolve().parent
TEMPLATE_PATH = ROOT / "template.html"
CASES_DIR = ROOT / "cases"
EXAMPLES_DIR = ROOT / "examples"


def _script_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def render_case(case_path: Path) -> str:
    config = normalize_config(json.loads(case_path.read_text(encoding="utf-8")))
    model = assert_physics(config, derive_physics(config))
    source = TEMPLATE_PATH.read_text(encoding="utf-8")
    replacements = {
        "__DOCUMENT_TITLE__": html.escape(config["title"], quote=True),
        "__CONFIG_JSON__": _script_json(config),
        "__MODEL_JSON__": _script_json(model),
    }
    for marker, value in replacements.items():
        if source.count(marker) != 1:
            raise RuntimeError(f"模板标记 {marker} 应恰好出现一次")
        source = source.replace(marker, value)
    if "__CONFIG_JSON__" in source or "__MODEL_JSON__" in source:
        raise RuntimeError("模板仍有未替换标记")
    return source


def expected_outputs() -> dict[Path, str]:
    outputs: dict[Path, str] = {}
    for case_path in sorted(CASES_DIR.glob("*.json")):
        outputs[EXAMPLES_DIR / case_path.stem / "index.html"] = render_case(case_path)
    if len(outputs) < 2:
        raise RuntimeError("至少需要两组模板实例")
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="只检查落盘实例是否与模板一致")
    args = parser.parse_args()

    stale: list[Path] = []
    for output_path, content in expected_outputs().items():
        if args.check:
            if not output_path.exists() or output_path.read_text(encoding="utf-8") != content:
                stale.append(output_path)
        else:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(content, encoding="utf-8")
            print(f"已生成：{output_path.relative_to(ROOT)}")
    if stale:
        for path in stale:
            print(f"实例过期或缺失：{path.relative_to(ROOT)}")
        return 1
    if args.check:
        print("模板实例与配置一致。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
