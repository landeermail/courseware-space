#!/usr/bin/env python3
"""Validate the repository's static GitHub Pages structure without dependencies."""

from __future__ import annotations

import argparse
import ast
from html.parser import HTMLParser
import json
from pathlib import Path
import posixpath
import re
import sys
from typing import Iterable
from urllib.parse import unquote, urlsplit


COURSEWARE_DATA = re.compile(r"\bconst\s+coursewareData\s*=\s*")
CORE_ASSETS = re.compile(
    r"\b(?:const|let|var)\s+CORE_ASSETS\s*=\s*(\[[\s\S]*?\])\s*;"
)
IGNORED_SCHEMES = {
    "blob",
    "data",
    "http",
    "https",
    "javascript",
    "mailto",
    "tel",
}
DYNAMIC_MARKERS = ("${", "{{", "<%")


class ReferenceParser(HTMLParser):
    """Collect literal href and src attributes with their source line."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.references: list[tuple[int, str, str, str]] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        self._collect(tag, attrs)

    def handle_startendtag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        self._collect(tag, attrs)

    def _collect(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        line, _ = self.getpos()
        for name, value in attrs:
            if name in {"href", "src"} and value is not None:
                self.references.append((line, tag, name, value))


class SiteValidator:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.errors: list[str] = []
        self.homepage_entries = 0
        self.html_references = 0
        self.manifest_references = 0
        self.service_worker_references = 0

    def error(self, source: Path, message: str, line: int | None = None) -> None:
        location = source.relative_to(self.root).as_posix()
        if line is not None:
            location += f":{line}"
        self.errors.append(f"{location}: {message}")

    def validate(self) -> bool:
        self.validate_homepage()
        for html_file in sorted(self.root.rglob("*.html")):
            self.validate_html(html_file)
        for manifest in sorted(self.root.rglob("*.webmanifest")):
            self.validate_manifest(manifest)
        for service_worker in sorted(self.root.rglob("sw.js")):
            self.validate_service_worker(service_worker)
        return not self.errors

    def validate_homepage(self) -> None:
        homepage = self.root / "index.html"
        if not homepage.is_file():
            self.error(homepage, "仓库根目录缺少 index.html")
            return

        text = homepage.read_text(encoding="utf-8")
        assignment = COURSEWARE_DATA.search(text)
        if assignment is None:
            self.error(homepage, "找不到 const coursewareData = ...")
            return

        try:
            data, _ = json.JSONDecoder().raw_decode(text, assignment.end())
        except json.JSONDecodeError as exc:
            line = text.count("\n", 0, assignment.end() + exc.pos) + 1
            self.error(homepage, f"coursewareData 不是有效 JSON：{exc.msg}", line)
            return

        categories = data.get("categories") if isinstance(data, dict) else None
        if not isinstance(categories, list):
            self.error(homepage, "coursewareData.categories 必须是数组")
            return

        for category_index, category in enumerate(categories, start=1):
            lessons = category.get("lessons") if isinstance(category, dict) else None
            if not isinstance(lessons, list):
                self.error(
                    homepage,
                    f"第 {category_index} 个分类的 lessons 必须是数组",
                )
                continue
            for lesson_index, lesson in enumerate(lessons, start=1):
                label = f"第 {category_index} 个分类的第 {lesson_index} 张卡片"
                if not isinstance(lesson, dict):
                    self.error(homepage, f"{label}必须是对象")
                    continue
                title = lesson.get("title")
                if not isinstance(title, str) or not title.strip():
                    self.error(homepage, f"{label}缺少字符串 title")
                entries = lesson.get("entries")
                if not isinstance(entries, list) or not entries:
                    self.error(homepage, f"{label}的 entries 必须是非空数组")
                    continue
                for entry_index, entry in enumerate(entries, start=1):
                    self.homepage_entries += 1
                    entry_label = f"{label}的第 {entry_index} 个入口"
                    if not isinstance(entry, dict):
                        self.error(homepage, f"{entry_label}必须是对象")
                        continue
                    entry_title = entry.get("title")
                    if not isinstance(entry_title, str) or not entry_title.strip():
                        self.error(homepage, f"{entry_label}缺少字符串 title")
                    path = entry.get("path")
                    if not isinstance(path, str) or not path:
                        self.error(homepage, f"{entry_label}缺少字符串 path")
                        continue
                    parsed = urlsplit(path)
                    if parsed.scheme or parsed.netloc or path.startswith("/"):
                        self.error(
                            homepage,
                            f"{entry_label}的 path 必须是相对路径：{path!r}",
                        )
                        continue
                    if parsed.query or parsed.fragment:
                        self.error(
                            homepage,
                            f"{entry_label}的 path 不能包含查询或锚点：{path!r}",
                        )
                    if not parsed.path.endswith("/"):
                        self.error(
                            homepage,
                            f"{entry_label}的 path 必须以 / 结尾：{path!r}",
                        )
                    self.check_reference(
                        homepage,
                        path,
                        context=f"首页课件路径 {path!r}",
                        require_directory_index=True,
                    )

    def validate_html(self, html_file: Path) -> None:
        parser = ReferenceParser()
        try:
            parser.feed(html_file.read_text(encoding="utf-8"))
            parser.close()
        except (OSError, UnicodeError) as exc:
            self.error(html_file, f"无法读取 HTML：{exc}")
            return

        for line, tag, attribute, value in parser.references:
            if self.reference_path(value) is None:
                continue
            self.html_references += 1
            self.check_reference(
                html_file,
                value,
                context=f"<{tag}> 的 {attribute}={value!r}",
                line=line,
                require_directory_index=True,
            )

    def validate_manifest(self, manifest: Path) -> None:
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            self.error(manifest, f"无法解析 Web Manifest：{exc}")
            return

        if not isinstance(data, dict):
            self.error(manifest, "Web Manifest 顶层必须是对象")
            return

        for field, require_index in (("start_url", True), ("scope", False)):
            value = data.get(field)
            if value is None:
                continue
            if not isinstance(value, str):
                self.error(manifest, f"{field} 必须是字符串")
                continue
            if self.reference_path(value) is None:
                continue
            self.manifest_references += 1
            self.check_reference(
                manifest,
                value,
                context=f"{field}={value!r}",
                require_directory_index=require_index,
            )

        icons = data.get("icons", [])
        if not isinstance(icons, list):
            self.error(manifest, "icons 必须是数组")
            return
        for index, icon in enumerate(icons, start=1):
            source = icon.get("src") if isinstance(icon, dict) else None
            if not isinstance(source, str) or not source:
                self.error(manifest, f"第 {index} 个 icon 缺少字符串 src")
                continue
            if self.reference_path(source) is None:
                continue
            self.manifest_references += 1
            self.check_reference(
                manifest,
                source,
                context=f"第 {index} 个 icon 的 src={source!r}",
                require_directory_index=False,
            )

    def validate_service_worker(self, service_worker: Path) -> None:
        try:
            text = service_worker.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            self.error(service_worker, f"无法读取 Service Worker：{exc}")
            return

        match = CORE_ASSETS.search(text)
        if match is None:
            return
        try:
            assets = ast.literal_eval(match.group(1))
        except (SyntaxError, ValueError) as exc:
            line = text.count("\n", 0, match.start(1)) + 1
            self.error(service_worker, f"无法解析 CORE_ASSETS：{exc}", line)
            return
        if not isinstance(assets, (list, tuple)) or not all(
            isinstance(asset, str) for asset in assets
        ):
            line = text.count("\n", 0, match.start(1)) + 1
            self.error(service_worker, "CORE_ASSETS 必须是字符串数组", line)
            return

        for asset in assets:
            if self.reference_path(asset) is None:
                continue
            self.service_worker_references += 1
            self.check_reference(
                service_worker,
                asset,
                context=f"CORE_ASSETS 中的 {asset!r}",
                require_directory_index=True,
            )

    @staticmethod
    def reference_path(reference: str) -> str | None:
        value = reference.strip()
        if not value or value.startswith(("#", "//")):
            return None
        if any(marker in value for marker in DYNAMIC_MARKERS):
            return None
        parsed = urlsplit(value)
        if parsed.scheme.lower() in IGNORED_SCHEMES or parsed.netloc:
            return None
        if parsed.scheme:
            return None
        path = unquote(parsed.path)
        return path or None

    def check_reference(
        self,
        source: Path,
        reference: str,
        *,
        context: str,
        require_directory_index: bool,
        line: int | None = None,
    ) -> None:
        path = self.reference_path(reference)
        if path is None:
            return
        if "\\" in path:
            self.error(source, f"{context} 使用了反斜杠路径", line)
            return

        source_directory = source.parent.relative_to(self.root).as_posix()
        if path.startswith("/"):
            relative = posixpath.normpath(path.lstrip("/"))
        else:
            relative = posixpath.normpath(posixpath.join(source_directory, path))

        if relative == ".." or relative.startswith("../"):
            self.error(source, f"{context} 指向仓库外部", line)
            return

        target = self.case_sensitive_path(relative)
        if target is None:
            self.error(source, f"{context} 找不到对应的本地路径", line)
            return

        if target.is_dir() and require_directory_index:
            index_relative = posixpath.join(relative, "index.html")
            if self.case_sensitive_path(index_relative) is None:
                self.error(source, f"{context} 指向的目录缺少 index.html", line)

    def case_sensitive_path(self, relative: str) -> Path | None:
        current = self.root
        if relative in {"", "."}:
            return current
        for part in relative.split("/"):
            if part in {"", "."}:
                continue
            if part == ".." or not current.is_dir():
                return None
            children = {child.name: child for child in current.iterdir()}
            if part not in children:
                return None
            current = children[part]
        return current


def format_summary(validator: SiteValidator) -> str:
    return (
        f"{validator.homepage_entries} 个首页课件路径，"
        f"{validator.html_references} 个 HTML 本地引用，"
        f"{validator.manifest_references} 个 Manifest 本地引用，"
        f"{validator.service_worker_references} 个 Service Worker 预缓存引用"
    )


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "root",
        nargs="?",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="仓库根目录（默认根据脚本位置推断）",
    )
    return parser.parse_args(argv)


def main(argv: Iterable[str] = sys.argv[1:]) -> int:
    args = parse_args(argv)
    root = args.root.resolve()
    validator = SiteValidator(root)
    if validator.validate():
        print(f"静态站点校验通过：{format_summary(validator)}。")
        return 0

    print(f"静态站点校验失败，共 {len(validator.errors)} 项：", file=sys.stderr)
    for error in sorted(validator.errors):
        print(f"- {error}", file=sys.stderr)
    print(f"已扫描：{format_summary(validator)}。", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
