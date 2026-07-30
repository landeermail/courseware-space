#!/usr/bin/env python3
"""Build local-only trial question pages from a private manifest and DOCX assets."""

from __future__ import annotations

import argparse
from html import escape
import json
from pathlib import Path
import re
import shutil
import sys
from zipfile import BadZipFile, ZipFile


HERE = Path(__file__).resolve().parent
DEFAULT_OUTPUT = HERE / "private" / "questions"
TEMPLATE = HERE / "question-template.html"
QUESTION_ID = re.compile(r"^q[0-9]{2}-[a-z0-9]+(?:-[a-z0-9]+)*$")
IMAGE_MEMBER = re.compile(r"^word/media/[A-Za-z0-9_.-]+\.png$")
FORBIDDEN_CONTENT = re.compile(
    r"【\s*(?:答案|解析|详解)\s*】|正确答案|故选", re.IGNORECASE
)
UNSAFE_HTML = re.compile(
    r"<(?:script|iframe|object|embed|form|base)\b|\bon[a-z]+\s*=|(?:https?:)?//",
    re.IGNORECASE,
)


class MaterialError(ValueError):
    pass


def _exact_keys(value: object, expected: set[str], label: str) -> None:
    if not isinstance(value, dict):
        raise MaterialError(f"{label} 必须是对象")
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise MaterialError(f"{label} 字段不匹配，缺少={missing}，多余={extra}")


def _private_output(path: Path) -> Path:
    resolved = path.resolve()
    private_root = (HERE / "private").resolve()
    if resolved != private_root and private_root not in resolved.parents:
        raise MaterialError("输出目录必须位于 trial/private/ 内，防止内部材料进入公开路径")
    return resolved


def _load_manifest(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise MaterialError(f"无法读取私有 manifest：{error}") from error
    _exact_keys(payload, {"schema_version", "source_label", "questions"}, "manifest")
    if payload["schema_version"] != 1:
        raise MaterialError("manifest.schema_version 必须为 1")
    if not isinstance(payload["source_label"], str) or not payload["source_label"].strip():
        raise MaterialError("source_label 不能为空")
    questions = payload["questions"]
    if not isinstance(questions, list) or len(questions) != 3:
        raise MaterialError("第一次试用 manifest 必须恰好包含 3 道题")
    return payload


def _validate_question(question: object, index: int) -> dict[str, str]:
    label = f"questions[{index}]"
    expected = {"id", "number", "title", "content_html", "image_member", "image_alt"}
    _exact_keys(question, expected, label)
    assert isinstance(question, dict)
    for key in expected:
        if not isinstance(question[key], str) or not question[key].strip():
            raise MaterialError(f"{label}.{key} 不能为空")
    if not QUESTION_ID.fullmatch(question["id"]):
        raise MaterialError(f"{label}.id 格式无效")
    if not IMAGE_MEMBER.fullmatch(question["image_member"]):
        raise MaterialError(f"{label}.image_member 只能引用 DOCX 内的 PNG")
    content = question["content_html"]
    if FORBIDDEN_CONTENT.search(content):
        raise MaterialError(f"{label}.content_html 疑似包含答案或解析")
    if UNSAFE_HTML.search(content):
        raise MaterialError(f"{label}.content_html 包含不安全或外部内容")
    return {key: question[key] for key in expected}


def build(source_docx: Path, manifest_path: Path, output_root: Path) -> list[Path]:
    output_root = _private_output(output_root)
    manifest = _load_manifest(manifest_path)
    template = TEMPLATE.read_text(encoding="utf-8")
    required_tokens = {
        "{{TITLE}}",
        "{{NUMBER}}",
        "{{CONTENT}}",
        "{{IMAGE_SOURCE}}",
        "{{IMAGE_ALT}}",
        "{{SOURCE_LABEL}}",
    }
    missing_tokens = sorted(token for token in required_tokens if token not in template)
    if missing_tokens:
        raise MaterialError(f"题页模板缺少占位符：{missing_tokens}")

    try:
        archive = ZipFile(source_docx)
    except (OSError, BadZipFile) as error:
        raise MaterialError(f"无法打开 DOCX：{error}") from error

    built: list[Path] = []
    seen: set[str] = set()
    with archive:
        members = set(archive.namelist())
        for index, raw in enumerate(manifest["questions"], start=1):
            question = _validate_question(raw, index)
            if question["id"] in seen:
                raise MaterialError(f"题目 ID 重复：{question['id']}")
            seen.add(question["id"])
            if question["image_member"] not in members:
                raise MaterialError(f"DOCX 缺少图片：{question['image_member']}")

            target = output_root / question["id"]
            if target.exists():
                shutil.rmtree(target)
            target.mkdir(parents=True)
            (target / "diagram.png").write_bytes(archive.read(question["image_member"]))
            page = template
            replacements = {
                "{{TITLE}}": escape(question["title"]),
                "{{NUMBER}}": escape(question["number"]),
                "{{CONTENT}}": question["content_html"],
                "{{IMAGE_SOURCE}}": "diagram.png",
                "{{IMAGE_ALT}}": escape(question["image_alt"]),
                "{{SOURCE_LABEL}}": escape(str(manifest["source_label"])),
            }
            for token, value in replacements.items():
                page = page.replace(token, value)
            (target / "index.html").write_text(page, encoding="utf-8")
            built.append(target / "index.html")
    return built


def main() -> int:
    parser = argparse.ArgumentParser(description="生成不进入 Git 的老师私有试题页")
    parser.add_argument("--source-docx", required=True, type=Path)
    parser.add_argument("--manifest", default=HERE / "private" / "questions.json", type=Path)
    parser.add_argument("--output", default=DEFAULT_OUTPUT, type=Path)
    args = parser.parse_args()
    try:
        built = build(args.source_docx.resolve(), args.manifest.resolve(), args.output)
    except MaterialError as error:
        print(f"生成失败：{error}", file=sys.stderr)
        return 1
    for path in built:
        print(f"已生成：{path.relative_to(HERE.parent)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
