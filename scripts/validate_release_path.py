#!/usr/bin/env python3
"""Release-path gate: candidate identity checks and live real-path checks.

candidate 模式：发布前验证精确 revision 与候选工件的一致性。
live 模式：发布后从真实 Pages 题库入口跟随 courseware 链接验证线上工件，
不接受调用者直接传入课件 URL 冒充真实路径。

输出只包含脱敏相对路径与判定；绝不打印 fragment、访问码或完整私密 URL。
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path
from typing import Callable
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

REVISION_RE = re.compile(r"^(?P<course>[a-z0-9]+)-v(?P<major>\d+)-(?P<digest>[0-9a-f]{12})$")
ENTRY_RE = re.compile(r"\{id:'(?P<id>[^']+)'[^{}]*?href:'(?P<href>[^']+)'")
TITLE_RE = re.compile(r"<title>(?P<title>[^<]*)</title>")
META_TAG_RE = re.compile(r"<meta\b[^>]*>", re.IGNORECASE)
ATTR_RE = re.compile(r"([a-zA-Z-]+)\s*=\s*\"([^\"]*)\"")
INTERNAL_VERSION_RE = re.compile(
    r"window\.__[A-Za-z0-9_$]+\s*=\s*\{[^{}]*?version\s*:\s*'([^']+)'",
    re.DOTALL,
)
RESOURCE_RE = re.compile(r"(?:src|href)\s*=\s*\"([^\"]+)\"")
FEEDBACK_HREF_RE = re.compile(r"href\s*=\s*\"([^\"]*feedback[^\"]*)\"")

ROBOTS_CONTENT = "noindex,nofollow,noarchive"
REFERRER_CONTENT = "no-referrer"


class Report:
    """收集判定结果；details 只允许脱敏相对路径与状态。"""

    def __init__(self) -> None:
        self.failures: list[str] = []
        self.oks: list[str] = []

    def ok(self, name: str) -> None:
        self.oks.append(name)

    def fail(self, name: str, detail: str) -> None:
        self.failures.append(f"{name}: {detail}")

    @property
    def passed(self) -> bool:
        return not self.failures


def parse_revision(revision: str) -> tuple[str, str, str]:
    match = REVISION_RE.fullmatch(revision)
    if not match:
        raise ValueError("revision 格式必须为 <course>-v<N>-<12位十六进制>")
    return match.group("course"), match.group("major"), match.group("digest")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def extract_title(html: str) -> str | None:
    match = TITLE_RE.search(html)
    return match.group("title").strip() if match else None


def extract_internal_version(html: str) -> str | None:
    match = INTERNAL_VERSION_RE.search(html)
    return match.group(1) if match else None


def extract_metas(html: str) -> dict[str, str]:
    metas: dict[str, str] = {}
    for tag in META_TAG_RE.findall(html):
        attrs = dict(ATTR_RE.findall(tag))
        name = attrs.get("name")
        if name and "content" in attrs:
            metas[name.lower()] = attrs["content"]
    return metas


def parse_library_entries(html: str) -> dict[str, str]:
    return {match.group("id"): match.group("href") for match in ENTRY_RE.finditer(html)}


def version_token_check(text: str, major: str) -> bool:
    return re.search(rf"(?<![A-Za-z0-9])v{major}(?![A-Za-z0-9])", text) is not None


def check_version_semantics(report: Report, html: str, course: str, major: str, where: str) -> None:
    title = extract_title(html)
    if title is None:
        report.fail("title-present", f"{where} 缺少 <title>")
    elif not version_token_check(title, major):
        report.fail("title-version", f"{where} 标题版本与 revision 语义不一致")
    internal = extract_internal_version(html)
    expected_internal = f"{course}-v{major}"
    if internal is None:
        report.fail("internal-version-present", f"{where} 缺少内部版本字段")
    elif internal != expected_internal:
        report.fail("internal-version", f"{where} 内部版本字段与 revision 语义不一致")


def check_candidate(
    revision: str,
    courseware_id: str,
    preview_path: Path,
    private_path: Path,
    library_path: Path,
) -> Report:
    report = Report()
    course, major, digest = parse_revision(revision)
    if courseware_id != course and not courseware_id.startswith(course + "-"):
        report.fail("revision-courseware", "revision 与 courseware id 不对应")
        return report

    preview_bytes = preview_path.read_bytes()
    private_bytes = private_path.read_bytes()
    preview_html = preview_bytes.decode("utf-8")

    # 1. revision 后 12 位等于候选 HTML SHA 前 12 位
    if sha256_bytes(preview_bytes)[:12] != digest:
        report.fail("revision-hash", "revision 后缀与候选 SHA 前 12 位不一致")
    else:
        report.ok("revision-hash")

    # 2. revision 语义版本、<title> 与内部版本字段一致
    before = len(report.failures)
    check_version_semantics(report, preview_html, course, major, "preview")
    if len(report.failures) == before:
        report.ok("version-semantics")

    # 3. 两份候选字节一致
    if preview_bytes != private_bytes:
        report.fail("candidate-byte-identity", "preview 与私有候选字节不一致")
    else:
        report.ok("candidate-byte-identity")

    # 4. preview 含精确 robots/referrer meta
    metas = extract_metas(preview_html)
    if metas.get("robots") != ROBOTS_CONTENT:
        report.fail("robots-meta", "preview 缺少精确 robots noindex,nofollow,noarchive")
    elif metas.get("referrer") != REFERRER_CONTENT:
        report.fail("referrer-meta", "preview 缺少精确 referrer no-referrer")
    else:
        report.ok("privacy-metas")

    # 5. 题库中指定 courseware id 的 href 本地解析到该 preview 候选
    entries = parse_library_entries(library_path.read_text(encoding="utf-8"))
    href = entries.get(courseware_id)
    if href is None:
        report.fail("library-entry", "题库中找不到指定 courseware id")
    elif urlsplit(href).scheme or href.startswith("/"):
        report.fail("library-href-scope", "题库 href 不是相对路径")
    else:
        resolved = (library_path.parent / href / "index.html").resolve()
        if resolved != preview_path.resolve():
            report.fail("library-href-target", "题库 href 未解析到该 preview 候选")
        else:
            report.ok("library-href-target")

    return report


FetchResult = tuple[int, bytes]
Fetcher = Callable[[str], FetchResult]


def http_fetch(url: str) -> FetchResult:
    request = Request(url, method="GET")
    try:
        with urlopen(request, timeout=30) as response:
            return response.status, response.read()
    except HTTPError as error:
        return error.code, b""
    except URLError as error:
        raise RuntimeError("网络请求失败") from error


def check_live(
    revision: str,
    courseware_id: str,
    library_url: str,
    fetch: Fetcher = http_fetch,
    expect_sha256: str | None = None,
) -> Report:
    report = Report()
    course, major, digest = parse_revision(revision)
    if courseware_id != course and not courseware_id.startswith(course + "-"):
        report.fail("revision-courseware", "revision 与 courseware id 不对应")
        return report

    # 1. 真实题库 URL 不得携带 fragment 或访问码
    split = urlsplit(library_url)
    if split.fragment or "access" in split.query.lower():
        report.fail("library-url-clean", "题库 URL 携带 fragment 或访问码")
        return report

    # 2. 从题库页解析指定 id 的实际 href 并跟随
    status, body = fetch(library_url)
    if status != 200:
        report.fail("library-fetch", f"题库页 HTTP {status}")
        return report
    entries = parse_library_entries(body.decode("utf-8"))
    href = entries.get(courseware_id)
    if href is None:
        report.fail("library-entry", "题库中找不到指定 courseware id")
        return report
    target_url = urljoin(library_url, href)
    target_split = urlsplit(target_url)
    if (target_split.scheme, target_split.netloc) != (split.scheme, split.netloc):
        report.fail("library-href-origin", "题库 href 指向题库源之外")
        return report
    report.ok("library-href-followed")

    # 3. 验证线上工件状态、SHA、标题与内部版本
    status, q01_bytes = fetch(target_url)
    if status != 200:
        report.fail("courseware-fetch", f"courseware 页 HTTP {status}")
        return report
    live_sha = sha256_bytes(q01_bytes)
    if expect_sha256 is not None and live_sha != expect_sha256:
        report.fail("live-sha", "线上 SHA 与期望完整哈希不一致")
    elif live_sha[:12] != digest:
        report.fail("live-sha", "线上 SHA 与 revision 后缀不一致")
    else:
        report.ok("live-sha")
    q01_html = q01_bytes.decode("utf-8")
    before = len(report.failures)
    check_version_semantics(report, q01_html, course, major, "live")
    if len(report.failures) == before:
        report.ok("live-version-semantics")

    # 4. 全部相对资源与评价入口为 200（输出只用相对路径）
    bad_resources: list[str] = []
    for ref in RESOURCE_RE.findall(q01_html):
        if ref.startswith(("http://", "https://", "data:", "#")):
            continue
        resource_status, _ = fetch(urljoin(target_url, ref))
        if resource_status != 200:
            bad_resources.append(ref)
    if bad_resources:
        report.fail("relative-resources", f"相对资源非 200：{sorted(bad_resources)}")
    else:
        report.ok("relative-resources")

    feedback_links = [link for link in FEEDBACK_HREF_RE.findall(q01_html) if not link.startswith("#")]
    if not feedback_links:
        report.fail("feedback-entry", "找不到评价入口链接")
    else:
        bad_feedback = []
        for link in feedback_links:
            feedback_status, _ = fetch(link)
            if feedback_status != 200:
                bad_feedback.append(urlsplit(link).path)
        if bad_feedback:
            report.fail("feedback-entry", f"评价入口非 200：{sorted(bad_feedback)}")
        else:
            report.ok("feedback-entry")

    return report


def print_report(report: Report) -> None:
    for name in report.oks:
        print(f"ok {name}")
    for failure in report.failures:
        print(f"FAIL {failure}")


def main() -> int:
    parser = argparse.ArgumentParser(description="发布路径门禁：候选一致性与真实路径线上核验")
    subparsers = parser.add_subparsers(dest="command", required=True)

    candidate_parser = subparsers.add_parser("candidate")
    candidate_parser.add_argument("--revision", required=True)
    candidate_parser.add_argument("--courseware-id", required=True)
    candidate_parser.add_argument("--preview", type=Path, required=True)
    candidate_parser.add_argument("--private", type=Path, required=True)
    candidate_parser.add_argument("--library", type=Path, required=True)

    live_parser = subparsers.add_parser("live")
    live_parser.add_argument("--revision", required=True)
    live_parser.add_argument("--courseware-id", required=True)
    live_parser.add_argument("--library-url", required=True)
    live_parser.add_argument("--expect-sha256", default=None)

    args = parser.parse_args()
    try:
        if args.command == "candidate":
            report = check_candidate(
                args.revision, args.courseware_id, args.preview, args.private, args.library
            )
        else:
            report = check_live(
                args.revision,
                args.courseware_id,
                args.library_url,
                expect_sha256=args.expect_sha256,
            )
    except (ValueError, RuntimeError, OSError) as error:
        print(f"FAIL gate-error: {error}", file=sys.stderr)
        return 2
    print_report(report)
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
