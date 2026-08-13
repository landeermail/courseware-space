#!/usr/bin/env python3
"""Build the GitHub Pages artifact from an explicit static-site allowlist."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import sys
from typing import Iterable


PUBLIC_PATHS = (
    Path(".nojekyll"),
    Path("index.html"),
    Path("electromagnetism/q6-plane"),
    Path("electromagnetism/q13-helicopter-physics"),
    Path("electromagnetism/q20-rotating-rod"),
    Path("electromagnetism/q21-variable-field-rod"),
    Path("electromagnetism/q21-variable-field-rod-3d"),
    Path("helicopter-dynamics/q13-helicopter"),
    Path("mechanics/q23-falling-tube-ball"),
    Path("mh370-physics/mh370-physics"),
    Path("preview/TNlUdPGF-r2ZDQ4ZDFWYHS8ERlIxaUJT"),
)

EXPECTED_TOP_LEVEL = frozenset(path.parts[0] for path in PUBLIC_PATHS)


class PagesBuildError(RuntimeError):
    """Raised when a Pages artifact cannot be built safely."""


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _validate_output(source_root: Path, output: Path) -> None:
    if output == source_root or _is_relative_to(source_root, output):
        raise PagesBuildError("输出目录不能是仓库根目录或其父目录")
    if _is_relative_to(output, source_root):
        first_part = output.relative_to(source_root).parts[0]
        if first_part in EXPECTED_TOP_LEVEL:
            raise PagesBuildError("输出目录不能位于白名单源目录内")


def _source_files(source_root: Path) -> dict[Path, Path]:
    files: dict[Path, Path] = {}
    for relative in PUBLIC_PATHS:
        source = source_root / relative
        if not source.exists():
            raise PagesBuildError(f"白名单源路径不存在：{relative.as_posix()}")
        if source.is_symlink():
            raise PagesBuildError(f"白名单源路径不能是符号链接：{relative.as_posix()}")
        candidates = [source] if source.is_file() else sorted(source.rglob("*"))
        for candidate in candidates:
            if candidate.is_symlink():
                child = candidate.relative_to(source_root).as_posix()
                raise PagesBuildError(f"白名单内容不能包含符号链接：{child}")
            if candidate.is_file():
                files[candidate.relative_to(source_root)] = candidate
    return files


def artifact_files(root: Path) -> set[Path]:
    return {
        path.relative_to(root)
        for path in root.rglob("*")
        if path.is_file() or path.is_symlink()
    }


def validate_pages_boundary(root: Path, expected_files: set[Path] | None = None) -> None:
    if not root.is_dir():
        raise PagesBuildError(f"Pages 工件目录不存在：{root}")

    actual_top_level = {path.name for path in root.iterdir()}
    if actual_top_level != EXPECTED_TOP_LEVEL:
        missing = sorted(EXPECTED_TOP_LEVEL - actual_top_level)
        unexpected = sorted(actual_top_level - EXPECTED_TOP_LEVEL)
        details = []
        if missing:
            details.append(f"缺少顶层路径：{', '.join(missing)}")
        if unexpected:
            details.append(f"出现非白名单顶层路径：{', '.join(unexpected)}")
        raise PagesBuildError("；".join(details))

    actual_files = artifact_files(root)
    symlinks = sorted(
        path.as_posix() for path in actual_files if (root / path).is_symlink()
    )
    if symlinks:
        raise PagesBuildError(f"Pages 工件包含符号链接：{', '.join(symlinks)}")

    if expected_files is not None and actual_files != expected_files:
        missing = sorted(path.as_posix() for path in expected_files - actual_files)
        unexpected = sorted(path.as_posix() for path in actual_files - expected_files)
        details = []
        if missing:
            details.append(f"缺少白名单文件：{', '.join(missing)}")
        if unexpected:
            details.append(f"出现非白名单文件：{', '.join(unexpected)}")
        raise PagesBuildError("；".join(details))


def build_pages(source_root: Path, output: Path) -> int:
    source_root = source_root.resolve()
    output = output.resolve()
    _validate_output(source_root, output)
    source_files = _source_files(source_root)

    if output.exists():
        if output.is_symlink() or not output.is_dir():
            raise PagesBuildError(f"输出路径必须是普通目录：{output}")
        shutil.rmtree(output)
    output.mkdir(parents=True)

    for relative, source in sorted(source_files.items()):
        destination = output / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    expected_files = set(source_files)
    validate_pages_boundary(output, expected_files)

    from validate_site import SiteValidator, format_summary

    validator = SiteValidator(output)
    if not validator.validate():
        messages = "\n".join(f"- {error}" for error in sorted(validator.errors))
        raise PagesBuildError(f"Pages 工件静态校验失败：\n{messages}")

    print(
        f"Pages 工件构建通过：{len(expected_files)} 个白名单文件；"
        f"{format_summary(validator)}。"
    )
    return len(expected_files)


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path, help="Pages 工件输出目录")
    parser.add_argument(
        "--source-root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help=argparse.SUPPRESS,
    )
    return parser.parse_args(argv)


def main(argv: Iterable[str] = sys.argv[1:]) -> int:
    args = parse_args(argv)
    try:
        build_pages(args.source_root, args.output)
    except (OSError, PagesBuildError) as exc:
        print(f"Pages 工件构建失败：{exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
