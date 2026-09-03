from __future__ import annotations

from pathlib import Path
import re
import unittest
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parent.parent
FORBIDDEN_ROOTS = {
    "BLOCKED.md",
    "CONTEXT.md",
    "PROGRESS.md",
    "docs",
    "production",
    "research",
    "services",
}
PAGES_PREFIX = "https://landeermail.github.io/courseware-space/"
MARKDOWN_LINK = re.compile(r"\]\((https://landeermail\.github\.io/courseware-space/[^)\s]*)\)")


class PublicRepositoryBoundaryTests(unittest.TestCase):
    def test_internal_roots_are_absent(self) -> None:
        present = sorted(name for name in FORBIDDEN_ROOTS if (ROOT / name).exists())
        self.assertEqual(present, [])

    def test_public_root_has_an_explicit_rights_notice(self) -> None:
        notice = (ROOT / "LICENSE.md").read_text(encoding="utf-8")
        self.assertIn("All rights reserved", notice)
        self.assertIn("does not grant an open-source license", notice)

    def test_showcase_links_resolve_to_published_courseware(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        urls = MARKDOWN_LINK.findall(readme)
        self.assertTrue(urls, "README 必须包含至少一个公开课件链接")
        for url in urls:
            relative = unquote(url.removeprefix(PAGES_PREFIX))
            self.assertTrue(relative, "README 不应链接已取消的 Pages 根首页")
            target = ROOT / "site" / relative
            if relative.endswith("/"):
                target /= "index.html"
            self.assertTrue(target.is_file(), f"README 课件链接不存在：{url}")


if __name__ == "__main__":
    unittest.main()
