#!/usr/bin/env python3
"""Validate the generated local-only question pages before a teacher trial."""

from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
import re
import sys


HERE = Path(__file__).resolve().parent
PRIVATE = HERE / "private" / "questions"
EXPECTED = {
    "q01-vertical-circle",
    "q03-cut-rope",
    "q11-bubble-chamber",
}
LEAK = re.compile(r"【\s*(?:答案|解析|详解)\s*】|正确答案|故选|>\s*(?:BD|AC)\s*<", re.IGNORECASE)


class QuestionParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_question = False
        self.depth = 0
        self.question_text: list[str] = []
        self.image_sources: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "section" and "question" in (attributes.get("class") or "").split():
            self.in_question = True
            self.depth = 1
        elif self.in_question:
            self.depth += 1
        if tag == "img" and attributes.get("src"):
            self.image_sources.append(attributes["src"] or "")

    def handle_endtag(self, tag: str) -> None:
        if self.in_question:
            self.depth -= 1
            if self.depth == 0:
                self.in_question = False

    def handle_data(self, data: str) -> None:
        if self.in_question:
            self.question_text.append(data)


def main() -> int:
    errors: list[str] = []
    if not PRIVATE.is_dir():
        print("私有题页尚未生成", file=sys.stderr)
        return 1
    actual = {path.name for path in PRIVATE.iterdir() if path.is_dir()}
    if actual != EXPECTED:
        errors.append(f"题页目录必须恰好为 {sorted(EXPECTED)}，当前为 {sorted(actual)}")

    for question_id in sorted(EXPECTED):
        root = PRIVATE / question_id
        page = root / "index.html"
        diagram = root / "diagram.png"
        if not page.is_file():
            errors.append(f"{question_id} 缺少 index.html")
            continue
        if not diagram.is_file() or diagram.stat().st_size == 0:
            errors.append(f"{question_id} 缺少有效 diagram.png")
        text = page.read_text(encoding="utf-8")
        parser = QuestionParser()
        parser.feed(text)
        parser.close()
        question_text = " ".join(parser.question_text)
        if not question_text.strip():
            errors.append(f"{question_id} 题干为空")
        if LEAK.search(question_text):
            errors.append(f"{question_id} 题干疑似泄露答案或解析")
        if parser.image_sources != ["diagram.png"]:
            errors.append(f"{question_id} 图片引用必须且只能为 diagram.png")
        if "这道题的好课件，必须让学生看到什么、做到什么？" not in text:
            errors.append(f"{question_id} 缺少统一试用问题")

    if errors:
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("私有题页校验通过：3/3，配图完整，题干无答案/解析泄露。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
