from __future__ import annotations

import hashlib
import importlib.util
import json
import threading
import unittest
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import tempfile


MODULE_PATH = Path(__file__).with_name("validate_release_path.py")
SPEC = importlib.util.spec_from_file_location("validate_release_path", MODULE_PATH)
gate = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(gate)

REPO_ROOT = Path(__file__).resolve().parents[1]
PREVIEW_DIR = REPO_ROOT / "site" / "preview" / "TNlUdPGF-r2ZDQ4ZDFWYHS8ERlIxaUJT"
REAL_PREVIEW = PREVIEW_DIR / "q01-v8-1c89623d5bf0" / "index.html"
REAL_LIBRARY = PREVIEW_DIR / "index.html"
REAL_REVISION = "q01-v8-1c89623d5bf0"
REAL_SHA256 = "1c89623d5bf0c1f5e4f1722a1799a2ea9a7b563849ca20d88b0e44585e583e45"
COURSEWARE_ID = "q01-vertical-circle"

METAS = (
    '  <meta name="robots" content="noindex,nofollow,noarchive">\n'
    '  <meta name="referrer" content="no-referrer">\n'
)


def candidate_html(title_version="v8", internal_version="q01-v8", metas=METAS, extra=""):
    return (
        "<!DOCTYPE html>\n<html lang=\"zh-CN\">\n<head>\n"
        "  <meta charset=\"UTF-8\">\n"
        f"{metas}"
        f"  <title>q01 竖直圆环双带电小球 — {title_version}</title>\n"
        "</head>\n<body>\n"
        "<script>\n"
        "    window.__q01 = {\n"
        f"      version:'{internal_version}', state,\n"
        "    };\n"
        "</script>\n"
        f"{extra}"
        "</body>\n</html>\n"
    )


def library_html(href="q01-vertical-circle/"):
    return (
        "<!DOCTYPE html>\n<html><head><title>题库</title></head><body>\n"
        "<script>\n"
        "const items=[\n"
        f"      {{id:'{COURSEWARE_ID}',subject:'力学',title:'第1题',href:'{href}',priority:true}},\n"
        "    ];\n"
        "</script>\n</body></html>\n"
    )


def revision_for(html_text: str, major="v8") -> str:
    digest = hashlib.sha256(html_text.encode("utf-8")).hexdigest()[:12]
    return f"q01-{major}-{digest}"


class CandidateFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.root = Path(self.tempdir.name)
        self.preview_dir = self.root / "preview" / "lib" / COURSEWARE_ID
        self.preview_dir.mkdir(parents=True)
        self.private_dir = self.root / "private" / COURSEWARE_ID
        self.private_dir.mkdir(parents=True)
        self.preview = self.preview_dir / "index.html"
        self.private = self.private_dir / "index.html"
        self.library = self.root / "preview" / "lib" / "index.html"

    def write_fixture(self, html=None, private_html=None, href="q01-vertical-circle/"):
        html = candidate_html() if html is None else html
        private_html = html if private_html is None else private_html
        self.preview.write_text(html, encoding="utf-8")
        self.private.write_text(private_html, encoding="utf-8")
        self.library.write_text(library_html(href), encoding="utf-8")
        return html

    def run_gate(self, revision):
        return gate.check_candidate(
            revision, COURSEWARE_ID, self.preview, self.private, self.library
        )


class CandidateGateTests(CandidateFixture):
    def test_correct_candidate_passes(self) -> None:
        html = self.write_fixture()
        report = self.run_gate(revision_for(html))
        self.assertTrue(report.passed, report.failures)

    def test_real_repository_release_entry_passes_in_clean_checkout(self) -> None:
        self.assertEqual(hashlib.sha256(REAL_PREVIEW.read_bytes()).hexdigest(), REAL_SHA256)
        report = gate.check_candidate(
            REAL_REVISION, COURSEWARE_ID, REAL_PREVIEW, REAL_PREVIEW, REAL_LIBRARY
        )
        self.assertTrue(report.passed, report.failures)

    def test_old_title_fails(self) -> None:
        html = self.write_fixture(html=candidate_html(title_version="v7"))
        report = self.run_gate(revision_for(html))
        self.assertFalse(report.passed)
        self.assertTrue(any(f.startswith("title-version") for f in report.failures))

    def test_title_version_suffix_is_not_an_exact_token(self) -> None:
        html = self.write_fixture(html=candidate_html(title_version="v8beta"))
        report = self.run_gate(revision_for(html))
        self.assertFalse(report.passed)
        self.assertTrue(any(f.startswith("title-version") for f in report.failures))

    def test_old_internal_version_fails(self) -> None:
        html = self.write_fixture(html=candidate_html(internal_version="q01-v7"))
        report = self.run_gate(revision_for(html))
        self.assertFalse(report.passed)
        self.assertTrue(any(f.startswith("internal-version") for f in report.failures))

    def test_revision_hash_mismatch_fails(self) -> None:
        self.write_fixture()
        report = self.run_gate("q01-v8-000000000000")
        self.assertFalse(report.passed)
        self.assertTrue(any(f.startswith("revision-hash") for f in report.failures))

    def test_wrong_library_href_fails(self) -> None:
        html = self.write_fixture(href="../../electromagnetism/q6-plane/")
        report = self.run_gate(revision_for(html))
        self.assertFalse(report.passed)
        self.assertTrue(any(f.startswith("library-href-target") for f in report.failures))

    def test_missing_privacy_metas_fail(self) -> None:
        html = self.write_fixture(html=candidate_html(metas=""))
        report = self.run_gate(revision_for(html))
        self.assertFalse(report.passed)
        self.assertTrue(any(f.startswith("robots-meta") for f in report.failures))

    def test_candidate_byte_mismatch_fails(self) -> None:
        html = self.write_fixture(private_html=candidate_html(extra="<!-- drift -->\n"))
        report = self.run_gate(revision_for(html))
        self.assertFalse(report.passed)
        self.assertTrue(
            any(f.startswith("candidate-byte-identity") for f in report.failures)
        )

    def test_non_q01_candidate_internal_version_is_supported(self) -> None:
        courseware_id = "q20-rotating-rod"
        html = candidate_html(title_version="v3", internal_version="q20-v3").replace(
            "window.__q01", "window.__courseware"
        )
        self.preview.write_text(html, encoding="utf-8")
        self.private.write_text(html, encoding="utf-8")
        self.library.write_text(
            library_html().replace(
                f"id:'{COURSEWARE_ID}'", f"id:'{courseware_id}'"
            ),
            encoding="utf-8",
        )
        revision = f"q20-v3-{hashlib.sha256(html.encode('utf-8')).hexdigest()[:12]}"

        report = gate.check_candidate(
            revision, courseware_id, self.preview, self.private, self.library
        )

        self.assertTrue(report.passed, report.failures)


def live_html(port: int, extra="") -> str:
    feedback = f"http://127.0.0.1:{port}/feedback/?courseware_id={COURSEWARE_ID}"
    return (
        "<!DOCTYPE html>\n<html lang=\"zh-CN\">\n<head>\n"
        "  <meta charset=\"UTF-8\">\n"
        "  <title>q01 竖直圆环双带电小球 — v8</title>\n"
        "  <link rel=\"stylesheet\" href=\"katex/katex.min.css\">\n"
        "</head>\n<body>\n"
        "<img src=\"q1-problem.png\">\n"
        "<script>\n"
        "    window.__q01 = {\n"
        "      version:'q01-v8', state,\n"
        "    };\n"
        "</script>\n"
        "<script src=\"katex/katex.min.js\"></script>\n"
        f"<footer><a href=\"{feedback}\">去评价 →</a></footer>\n"
        f"{extra}"
        "</body>\n</html>\n"
    )


class LiveFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.www = Path(self.tempdir.name)
        (self.www / COURSEWARE_ID / "katex").mkdir(parents=True)
        (self.www / COURSEWARE_ID / "katex" / "katex.min.css").write_text("css")
        (self.www / COURSEWARE_ID / "katex" / "katex.min.js").write_text("js")
        (self.www / COURSEWARE_ID / "q1-problem.png").write_bytes(b"\x89PNG")
        (self.www / "feedback").mkdir()
        (self.www / "feedback" / "index.html").write_text("<html>评价</html>")
        self.server = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            partial(SimpleHTTPRequestHandler, directory=str(self.www)),
        )
        self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.server_thread.start()
        self.addCleanup(self.server.shutdown)
        self.addCleanup(self.server.server_close)
        self.port = self.server.server_address[1]
        self.library_url = f"http://127.0.0.1:{self.port}/"
        self.fetched: list[str] = []

    def write_site(self, q01_html: str, href="q01-vertical-circle/") -> None:
        (self.www / "index.html").write_text(library_html(href), encoding="utf-8")
        (self.www / COURSEWARE_ID / "index.html").write_text(q01_html, encoding="utf-8")

    def recording_fetch(self, url: str):
        self.fetched.append(url)
        return gate.http_fetch(url)

    def run_live(self, revision: str, library_url: str | None = None):
        return gate.check_live(
            revision,
            COURSEWARE_ID,
            library_url or self.library_url,
            fetch=self.recording_fetch,
        )


class LiveGateTests(LiveFixture):
    def test_live_correct_candidate_passes(self) -> None:
        html = live_html(self.port)
        self.write_site(html)
        report = self.run_live(revision_for(html))
        self.assertTrue(report.passed, report.failures)

    def test_live_follows_library_href(self) -> None:
        html = live_html(self.port)
        self.write_site(html)
        report = self.run_live(revision_for(html))
        self.assertTrue(report.passed, report.failures)
        self.assertEqual(self.fetched[0], self.library_url)
        self.assertEqual(self.fetched[1], f"{self.library_url}{COURSEWARE_ID}/")

    def test_live_old_hash_fails(self) -> None:
        html = live_html(self.port, extra="<!-- stale artifact -->\n")
        self.write_site(html)
        report = self.run_live(revision_for(live_html(self.port)))
        self.assertFalse(report.passed)
        self.assertTrue(any(f.startswith("live-sha") for f in report.failures))

    def test_live_old_version_semantics_fail(self) -> None:
        html = live_html(self.port).replace("— v8", "— v7").replace("q01-v8", "q01-v7")
        self.write_site(html)
        report = self.run_live(revision_for(html))
        self.assertFalse(report.passed)
        self.assertTrue(any(f.startswith("title-version") for f in report.failures))
        self.assertTrue(any(f.startswith("internal-version") for f in report.failures))

    def test_live_rejects_fragment_or_access_in_library_url(self) -> None:
        html = live_html(self.port)
        self.write_site(html)
        report = self.run_live(
            revision_for(html), library_url=f"{self.library_url}#access=SECRET-CODE"
        )
        self.assertFalse(report.passed)
        self.assertTrue(any(f.startswith("library-url-clean") for f in report.failures))
        self.assertNotIn("SECRET-CODE", json.dumps(report.failures, ensure_ascii=False))
        self.assertEqual(self.fetched, [])

    def test_live_resource_404_fails(self) -> None:
        html = live_html(self.port)
        self.write_site(html)
        (self.www / COURSEWARE_ID / "q1-problem.png").unlink()
        report = self.run_live(revision_for(html))
        self.assertFalse(report.passed)
        self.assertTrue(any(f.startswith("relative-resources") for f in report.failures))

    def test_live_external_href_origin_fails(self) -> None:
        html = live_html(self.port)
        self.write_site(html, href="https://example.invalid/q01-vertical-circle/")
        report = self.run_live(revision_for(html))
        self.assertFalse(report.passed)
        self.assertTrue(any(f.startswith("library-href-origin") for f in report.failures))

    def test_live_feedback_404_fails(self) -> None:
        html = live_html(self.port)
        self.write_site(html)
        import shutil

        shutil.rmtree(self.www / "feedback")
        report = self.run_live(revision_for(html))
        self.assertFalse(report.passed)
        self.assertTrue(any(f.startswith("feedback-entry") for f in report.failures))


if __name__ == "__main__":
    unittest.main()
