#!/usr/bin/env python3
"""Validate courseware metadata and promote reviewed staging artifacts."""

from __future__ import annotations

import argparse
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MODULE_ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = MODULE_ROOT / "library" / "catalog.json"
STAGING_ROOT = MODULE_ROOT / "generator" / "staging"
LIBRARY_COURSEWARE_ROOT = MODULE_ROOT / "library" / "courseware"

REQUIRED_KEYS = {
    "schema_version",
    "id",
    "title",
    "owner",
    "status",
    "source_input_type",
    "physics_summary",
    "generated_at",
    "path",
    "review",
}
PHYSICS_KEYS = {
    "topic",
    "parameters",
    "magnetic_direction",
    "motion_direction",
    "current_direction",
    "asks",
}
REVIEW_KEYS = {"reviewer", "reviewed_at", "physics_confirmed"}
ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
PATH_PATTERN = re.compile(r"^[a-z0-9][A-Za-z0-9_./-]*/$")
STATUSES = {"pending_review", "published", "rejected"}
INPUT_TYPES = {"text", "image", "pdf", "manual"}


class MetadataError(ValueError):
    pass


def _timestamp(value: object, field: str, allow_null: bool = False) -> str | None:
    if allow_null and value is None:
        return None
    if not isinstance(value, str):
        raise MetadataError(f"{field} 必须是 ISO 8601 时间")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise MetadataError(f"{field} 不是有效 ISO 8601 时间") from error
    if parsed.tzinfo is None:
        raise MetadataError(f"{field} 必须包含时区")
    return value


def validate_metadata(raw: object, require_existing_page: bool = False, root: Path = MODULE_ROOT) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise MetadataError("元数据必须是 JSON 对象")
    if set(raw) != REQUIRED_KEYS:
        missing = REQUIRED_KEYS - set(raw)
        extra = set(raw) - REQUIRED_KEYS
        details = []
        if missing:
            details.append(f"缺少 {', '.join(sorted(missing))}")
        if extra:
            details.append(f"多出 {', '.join(sorted(extra))}")
        raise MetadataError("元数据字段不符合 schema：" + "；".join(details))
    if raw["schema_version"] != 1:
        raise MetadataError("schema_version 必须为 1")
    item_id = raw["id"]
    if not isinstance(item_id, str) or not 3 <= len(item_id) <= 80 or not ID_PATTERN.fullmatch(item_id):
        raise MetadataError("id 必须是小写英文、数字和连字符")
    title = raw["title"]
    if not isinstance(title, str) or not 4 <= len(title.strip()) <= 120:
        raise MetadataError("title 长度必须为 4～120")
    owner = raw["owner"]
    if not isinstance(owner, str) or not owner.strip() or len(owner.strip()) > 80:
        raise MetadataError("owner 必须是非空字符串")
    status = raw["status"]
    if status not in STATUSES:
        raise MetadataError("status 不在允许范围")
    if raw["source_input_type"] not in INPUT_TYPES:
        raise MetadataError("source_input_type 不在允许范围")
    path = raw["path"]
    if not isinstance(path, str) or not PATH_PATTERN.fullmatch(path) or ".." in Path(path).parts:
        raise MetadataError("path 必须是仓库内以 / 结尾的安全相对路径")
    _timestamp(raw["generated_at"], "generated_at")

    physics = raw["physics_summary"]
    if not isinstance(physics, dict) or set(physics) != PHYSICS_KEYS:
        raise MetadataError("physics_summary 字段不符合 schema")
    if not isinstance(physics["topic"], str) or len(physics["topic"].strip()) < 2:
        raise MetadataError("physics_summary.topic 不能为空")
    if not isinstance(physics["parameters"], dict):
        raise MetadataError("physics_summary.parameters 必须是对象")
    for key, value in physics["parameters"].items():
        if not isinstance(key, str) or not isinstance(value, (str, int, float, bool, type(None))):
            raise MetadataError("physics_summary.parameters 只允许标量")
    for field in ("magnetic_direction", "motion_direction", "current_direction"):
        value = physics[field]
        if value is not None and (not isinstance(value, str) or len(value) > 120):
            raise MetadataError(f"physics_summary.{field} 必须是文本或 null")
    asks = physics["asks"]
    if not isinstance(asks, list) or not asks or any(not isinstance(item, str) or not item.strip() for item in asks):
        raise MetadataError("physics_summary.asks 必须是非空文本数组")

    review = raw["review"]
    if not isinstance(review, dict) or set(review) != REVIEW_KEYS:
        raise MetadataError("review 字段不符合 schema")
    reviewer = review["reviewer"]
    if not isinstance(reviewer, str) or not reviewer.strip() or len(reviewer) > 80:
        raise MetadataError("review.reviewer 必须非空")
    _timestamp(review["reviewed_at"], "review.reviewed_at", allow_null=True)
    if not isinstance(review["physics_confirmed"], bool):
        raise MetadataError("review.physics_confirmed 必须是布尔值")
    if status == "published" and (not review["physics_confirmed"] or review["reviewed_at"] is None):
        raise MetadataError("published 课件必须经过物理确认并记录审核时间")
    if status == "pending_review" and review["physics_confirmed"]:
        raise MetadataError("pending_review 课件不能提前标记物理确认")

    if require_existing_page and not (root / path / "index.html").is_file():
        raise MetadataError(f"课件入口不存在：{path}index.html")
    return raw


def load_catalog(path: Path = CATALOG_PATH) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or set(data) != {"schema_version", "items"}:
        raise MetadataError("catalog 顶层字段不符合约定")
    if data["schema_version"] != 1 or not isinstance(data["items"], list):
        raise MetadataError("catalog schema_version/items 无效")
    return data


def validate_catalog(path: Path = CATALOG_PATH, root: Path = MODULE_ROOT) -> dict[str, Any]:
    catalog = load_catalog(path)
    ids: set[str] = set()
    paths: set[str] = set()
    for item in catalog["items"]:
        validate_metadata(item, require_existing_page=True, root=root)
        if item["id"] in ids:
            raise MetadataError(f"重复 id：{item['id']}")
        if item["path"] in paths:
            raise MetadataError(f"重复 path：{item['path']}")
        ids.add(item["id"])
        paths.add(item["path"])
    return catalog


class LibraryManager:
    def __init__(self, root: Path = MODULE_ROOT) -> None:
        self.root = root
        self.catalog_path = root / "library" / "catalog.json"
        self.staging_root = root / "generator" / "staging"
        self.courseware_root = root / "library" / "courseware"

    def promote(self, item_id: str, reviewer: str, accept_physics: bool) -> dict[str, Any]:
        if not accept_physics:
            raise MetadataError("晋升必须显式传入 --accept-physics")
        if not ID_PATTERN.fullmatch(item_id):
            raise MetadataError("课件 id 无效")
        staging_dir = self.staging_root / item_id
        metadata_path = staging_dir / "metadata.json"
        index_path = staging_dir / "index.html"
        if not metadata_path.is_file() or not index_path.is_file():
            raise MetadataError("staging 候选必须同时包含 metadata.json 和 index.html")
        if any(path.is_symlink() for path in staging_dir.rglob("*")):
            raise MetadataError("staging 候选不允许包含符号链接")
        metadata = validate_metadata(json.loads(metadata_path.read_text(encoding="utf-8")), root=self.root)
        if metadata["id"] != item_id or metadata["status"] != "pending_review":
            raise MetadataError("只能晋升同 id 的 pending_review 候选")
        if metadata["path"] != f"generator/staging/{item_id}/":
            raise MetadataError("staging metadata.path 与目录不一致")

        catalog = validate_catalog(self.catalog_path, root=self.root)
        if any(item["id"] == item_id for item in catalog["items"]):
            raise MetadataError("题库中已存在同 id 课件")
        destination = self.courseware_root / item_id
        if destination.exists():
            raise MetadataError("题库目标目录已存在")

        published = json.loads(json.dumps(metadata, ensure_ascii=False))
        published["status"] = "published"
        published["path"] = f"library/courseware/{item_id}/"
        published["review"] = {
            "reviewer": reviewer.strip(),
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
            "physics_confirmed": True,
        }
        validate_metadata(published, root=self.root)

        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(staging_dir, destination)
        (destination / "metadata.json").write_text(
            json.dumps(published, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        catalog["items"].append(published)
        catalog["items"].sort(key=lambda item: item["id"])
        temp_path = self.catalog_path.with_suffix(".json.tmp")
        temp_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temp_path.replace(self.catalog_path)
        validate_catalog(self.catalog_path, root=self.root)
        return published


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("validate")
    promote_parser = subparsers.add_parser("promote")
    promote_parser.add_argument("id")
    promote_parser.add_argument("--reviewer", required=True)
    promote_parser.add_argument("--accept-physics", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "validate":
            catalog = validate_catalog()
            print(f"题库元数据校验通过：{len(catalog['items'])} 个已发布课件，owner 8/8 非空。")
        else:
            published = LibraryManager().promote(args.id, args.reviewer, args.accept_physics)
            print(f"课件已晋升：{published['id']} → {published['path']}")
    except (MetadataError, OSError, json.JSONDecodeError) as error:
        print(f"题库操作失败：{error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
