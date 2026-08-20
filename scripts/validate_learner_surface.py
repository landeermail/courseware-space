#!/usr/bin/env python3
"""Check deterministic learner-surface copy and semantic-binding contracts."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
import re
import sys


RAW_NOTATION = re.compile(r"(?<![\w-])[A-Za-z][A-Za-z0-9]*_[A-Za-z0-9]+(?![\w-])")
INTERNAL_PHRASES = (
    "artifact 验证",
    "学生主路径",
    "机器代入",
    "物理参考模型误差",
    "不承担证明",
    "不用计算器",
)
SKIPPED_CONTENT = {"script", "style", "template"}
NATURALLY_FOCUSABLE = {"a", "button", "input", "select", "textarea"}
VOID_ELEMENTS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
    "meta", "param", "source", "track", "wbr",
}


@dataclass(frozen=True)
class Finding:
    line: int
    message: str


class LearnerSurfaceParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.findings: list[Finding] = []
        self.physics_ids: set[str] = set()
        self.physics_refs: list[tuple[int, str, str, dict[str, str]]] = []
        self._skipped_depth = 0
        self._internal_depth = 0
        self._context_stack: list[tuple[str, bool, bool]] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        self._start(tag, attrs)

    def handle_startendtag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        self._start(tag, attrs, self_closing=True)

    def handle_endtag(self, tag: str) -> None:
        self._end(tag)

    def _start(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
        *,
        self_closing: bool = False,
    ) -> None:
        attributes = {name: value or "" for name, value in attrs}
        adds_skipped = tag in SKIPPED_CONTENT
        adds_internal = attributes.get("data-audience") == "internal"
        if adds_skipped:
            self._skipped_depth += 1
        if adds_internal:
            self._internal_depth += 1
        if not self_closing and tag not in VOID_ELEMENTS:
            self._context_stack.append((tag, adds_skipped, adds_internal))

        line, _ = self.getpos()
        physics_id = attributes.get("data-physics-id", "").strip()
        if physics_id:
            self.physics_ids.add(physics_id)

        physics_ref = attributes.get("data-physics-ref", "").strip()
        if physics_ref:
            self.physics_refs.append((line, tag, physics_ref, attributes))

    def _end(self, tag: str) -> None:
        match = next(
            (
                index
                for index in range(len(self._context_stack) - 1, -1, -1)
                if self._context_stack[index][0] == tag
            ),
            None,
        )
        if match is None:
            return
        for _, added_skipped, added_internal in self._context_stack[match:]:
            if added_skipped:
                self._skipped_depth -= 1
            if added_internal:
                self._internal_depth -= 1
        del self._context_stack[match:]

    def handle_data(self, data: str) -> None:
        if self._skipped_depth or self._internal_depth or not data.strip():
            return
        line, _ = self.getpos()
        for match in RAW_NOTATION.finditer(data):
            self.findings.append(
                Finding(line, f"学习者可见裸源码符号 {match.group(0)!r}，请使用数学排版")
            )
        for phrase in INTERNAL_PHRASES:
            if phrase in data:
                self.findings.append(
                    Finding(line, f"学习者界面出现内部生产语言 {phrase!r}")
                )

    def finish(self) -> list[Finding]:
        for line, tag, raw_refs, attributes in self.physics_refs:
            for physics_ref in raw_refs.split():
                if physics_ref not in self.physics_ids:
                    self.findings.append(
                        Finding(line, f"data-physics-ref={physics_ref!r} 没有对应的 data-physics-id")
                    )
            if tag not in NATURALLY_FOCUSABLE and "tabindex" not in attributes:
                self.findings.append(
                    Finding(line, "图式绑定触发器必须可键盘聚焦（使用可聚焦元素或 tabindex）")
                )
        return sorted(self.findings, key=lambda finding: (finding.line, finding.message))


def validate_file(path: Path) -> list[Finding]:
    parser = LearnerSurfaceParser()
    parser.feed(path.read_text(encoding="utf-8"))
    parser.close()
    return parser.finish()


def main() -> int:
    argument_parser = argparse.ArgumentParser(
        description="检查学习者可见文案、数学源码泄漏和图式语义绑定"
    )
    argument_parser.add_argument("html", nargs="+", type=Path)
    args = argument_parser.parse_args()

    total = 0
    for path in args.html:
        try:
            findings = validate_file(path)
        except (OSError, UnicodeError) as exc:
            print(f"{path}: 无法读取：{exc}", file=sys.stderr)
            total += 1
            continue
        for finding in findings:
            print(f"{path}:{finding.line}: {finding.message}", file=sys.stderr)
        total += len(findings)

    if total:
        print(f"学习者表面检查失败：{total} 个确定性问题", file=sys.stderr)
        return 1
    print("学习者表面检查通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
