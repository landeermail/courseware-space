from __future__ import annotations

from html.parser import HTMLParser
import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]
PAGES = (
    ROOT / "electromagnetism" / "q21-variable-field-rod-3d" / "index.html",
    ROOT / "electromagnetism" / "q6-plane" / "index.html",
)
THREE_URL = "https://unpkg.com/three@0.160.0/build/three.module.js"
ORBIT_URL = "https://unpkg.com/three@0.160.0/examples/jsm/controls/OrbitControls.js"
THREE_INTEGRITY = "sha384-61S/Nu32S3E5+n+KpCOTb2eRYps6fVKm+9Gz1QBvSePFthb46f063Aa/qe/lykFZ"
ORBIT_INTEGRITY = "sha384-qlO/ZugKPxAQUAvTlQoo0QECzxJIJySZmCF/DHdb2Xn/hHndFwX/vfUAC9Hbk6LP"
TAILWIND_INTEGRITY = "sha384-igm5BeiBt36UU4gqwWS7imYmelpTsZlQ45FZf+XBn9MuJbn4nQr7yx1yFydocC/K"


class MetadataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.csp = ""
        self.scripts: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value or "" for key, value in attrs}
        if tag == "meta" and values.get("http-equiv") == "Content-Security-Policy":
            self.csp = values.get("content", "")
        if tag == "script" and values.get("src"):
            self.scripts.append(values)


def import_map(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    match = re.search(r'<script type="importmap">\s*(\{.*?\})\s*</script>', text, re.DOTALL)
    if not match:
        raise AssertionError(f"missing import map: {path}")
    return json.loads(match.group(1))


class ExternalScriptSecurityTests(unittest.TestCase):
    def test_three_and_orbit_controls_have_exact_integrity_metadata(self) -> None:
        for path in PAGES:
            with self.subTest(page=path.parent.name):
                integrity = import_map(path)["integrity"]
                self.assertEqual(integrity[THREE_URL], THREE_INTEGRITY)
                self.assertEqual(integrity[ORBIT_URL], ORBIT_INTEGRITY)

    def test_q6_tailwind_script_has_sri_and_anonymous_cors(self) -> None:
        parser = MetadataParser()
        parser.feed(PAGES[1].read_text(encoding="utf-8"))
        tailwind = [item for item in parser.scripts if item["src"] == "https://cdn.tailwindcss.com"]
        self.assertEqual(len(tailwind), 1)
        self.assertEqual(tailwind[0].get("integrity"), TAILWIND_INTEGRITY)
        self.assertEqual(tailwind[0].get("crossorigin"), "anonymous")

    def test_pages_have_restrictive_csp_for_declared_script_hosts(self) -> None:
        for path in PAGES:
            with self.subTest(page=path.parent.name):
                parser = MetadataParser()
                parser.feed(path.read_text(encoding="utf-8"))
                self.assertIn("default-src 'self'", parser.csp)
                self.assertIn("https://unpkg.com", parser.csp)
                self.assertIn("connect-src 'none'", parser.csp)
                self.assertIn("object-src 'none'", parser.csp)
                self.assertIn("base-uri 'none'", parser.csp)


if __name__ == "__main__":
    unittest.main()
