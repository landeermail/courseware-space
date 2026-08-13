#!/usr/bin/env python3
"""Create the task-scoped private OSS bucket and deliver static courseware."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import re
import secrets
import sys
from typing import Any
from urllib.parse import quote

try:
    import alibabacloud_oss_v2 as oss
except ImportError:  # Pure helpers remain importable by the dependency-free tests.
    oss = None  # type: ignore[assignment]


ROOT = Path(__file__).resolve().parents[1]
PRIVATE_ROOT = ROOT / "trial" / "private"
COURSEWARE_ROOT = PRIVATE_ROOT / "courseware"
DELIVERIES_FILE = PRIVATE_ROOT / "deliveries.json"
BUCKET = "courseware-space-private-10794778"
REGION = "cn-hangzhou"
PREFIX = "private/"
TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{48,}$")


def settings() -> tuple[str, str]:
    bucket = os.environ.get("COURSEWARE_PRIVATE_BUCKET", BUCKET).strip()
    region = os.environ.get("COURSEWARE_PRIVATE_REGION", REGION).strip()
    if bucket != BUCKET:
        raise ValueError(f"只允许操作任务 bucket：{BUCKET}")
    if region != REGION:
        raise ValueError(f"只允许使用任务区域：{REGION}")
    return bucket, region


def require_sdk() -> Any:
    if oss is None:
        raise RuntimeError("缺少临时 OSS SDK；请通过 deploy 下的 shell 入口执行")
    return oss


def client(region: str) -> Any:
    sdk = require_sdk()
    config = sdk.config.load_default()
    config.credentials_provider = sdk.credentials.EnvironmentVariableCredentialsProvider()
    config.region = region
    config.endpoint = f"https://oss-{region}.aliyuncs.com"
    return sdk.Client(config)


def unwrap_service_error(error: BaseException) -> Any | None:
    sdk = require_sdk()
    current: BaseException = error
    while isinstance(current, sdk.exceptions.OperationError):
        nested = current.unwrap()
        if not isinstance(nested, BaseException):
            return None
        current = nested
    return current if isinstance(current, sdk.exceptions.ServiceError) else None


def is_missing(error: BaseException) -> bool:
    service_error = unwrap_service_error(error)
    return bool(
        service_error
        and (
            service_error.status_code == 404
            or service_error.code
            in {"NoSuchBucket", "NoSuchBucketPolicy", "NoSuchPublicAccessBlockConfiguration"}
        )
    )


def policy_document(bucket: str, owner_id: str) -> dict[str, Any]:
    if not owner_id.isdigit():
        raise ValueError("OSS owner ID 格式无效")
    bucket_resource = f"acs:oss:*:{owner_id}:{bucket}"
    return {
        "Version": "1",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": ["*"],
                "Action": ["oss:GetObject"],
                "Resource": [f"{bucket_resource}/{PREFIX}*"],
            },
        ],
    }


def normalized_policy(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def inspect_bucket(api: Any, bucket: str) -> bool:
    sdk = require_sdk()
    try:
        api.get_bucket_info(sdk.GetBucketInfoRequest(bucket=bucket))
    except sdk.exceptions.BaseError as error:
        if is_missing(error):
            print("private_bucket=missing")
            return False
        raise
    print("private_bucket=existing")
    return True


def ensure_bucket(api: Any, bucket: str, region: str) -> None:
    sdk = require_sdk()
    created = False
    try:
        info_result = api.get_bucket_info(sdk.GetBucketInfoRequest(bucket=bucket))
    except sdk.exceptions.BaseError as error:
        if not is_missing(error):
            raise
        result = api.put_bucket(
            sdk.PutBucketRequest(
                bucket=bucket,
                acl="private",
                create_bucket_configuration=sdk.CreateBucketConfiguration(
                    storage_class="Standard",
                    data_redundancy_type="LRS",
                ),
            )
        )
        if not 200 <= result.status_code < 300:
            raise RuntimeError(f"创建 private bucket 失败（HTTP {result.status_code}）")
        created = True
        info_result = api.get_bucket_info(sdk.GetBucketInfoRequest(bucket=bucket))

    bucket_info = info_result.bucket_info
    if bucket_info is None or bucket_info.owner is None or not bucket_info.owner.id:
        raise RuntimeError("无法读取 private bucket owner")
    expected_location = f"oss-{region}"
    if bucket_info.location != expected_location:
        raise RuntimeError(f"private bucket 区域不符：{bucket_info.location}")
    acl = api.get_bucket_acl(sdk.GetBucketAclRequest(bucket=bucket)).acl
    if acl != "private":
        raise RuntimeError(f"private bucket ACL 必须为 private，实际为 {acl}")

    api.put_bucket_public_access_block(
        sdk.PutBucketPublicAccessBlockRequest(
            bucket=bucket,
            public_access_block_configuration=sdk.PublicAccessBlockConfiguration(
                block_public_access=False
            ),
        )
    )
    block_result = api.get_bucket_public_access_block(
        sdk.GetBucketPublicAccessBlockRequest(bucket=bucket)
    ).public_access_block_configuration
    if block_result is None or bool(block_result.block_public_access):
        raise RuntimeError("private bucket 仍阻止指定前缀的匿名读取")

    policy = policy_document(bucket, bucket_info.owner.id)
    policy_text = normalized_policy(policy)
    policy_result = api.put_bucket_policy(
        sdk.PutBucketPolicyRequest(bucket=bucket, body=policy_text)
    )
    if not 200 <= policy_result.status_code < 300:
        raise RuntimeError(f"配置 bucket policy 失败（HTTP {policy_result.status_code}）")
    read_back = api.get_bucket_policy(sdk.GetBucketPolicyRequest(bucket=bucket))
    body = read_back.body
    if hasattr(body, "read"):
        body = body.read()
    if isinstance(body, bytes):
        body = body.decode("utf-8")
    actual = json.loads(body)
    if normalized_policy(actual) != policy_text:
        raise RuntimeError("bucket policy 回读与期望不一致")
    print(f"private_bucket={'created' if created else 'verified'} acl=private region={region}")
    print("anonymous_policy=allow:GetObject(private/*) listing=default-deny")


def courseware_files(source: Path) -> list[tuple[Path, str]]:
    source = source.resolve()
    try:
        source.relative_to(COURSEWARE_ROOT.resolve())
    except ValueError as error:
        raise ValueError("只允许交付 trial/private/courseware/ 下的目录") from error
    if not source.is_dir() or not (source / "index.html").is_file():
        raise ValueError("课件目录不存在或缺少 index.html")
    symlinks = [path for path in source.rglob("*") if path.is_symlink()]
    if symlinks:
        raise ValueError("课件目录不能包含符号链接")
    files = [path for path in source.rglob("*") if path.is_file()]
    if not files:
        raise ValueError("课件目录为空")
    return [(path, path.relative_to(source).as_posix()) for path in sorted(files)]


def manifest_digest(files: list[tuple[Path, str]]) -> str:
    digest = hashlib.sha256()
    for path, relative in files:
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def content_type(relative: str) -> str:
    if relative.lower().endswith((".html", ".htm")):
        return "text/html; charset=utf-8"
    guessed, _ = mimetypes.guess_type(relative)
    if guessed and guessed.startswith("text/"):
        return f"{guessed}; charset=utf-8"
    if relative.lower().endswith(".json"):
        return "application/json; charset=utf-8"
    return guessed or "application/octet-stream"


def load_deliveries(path: Path = DELIVERIES_FILE) -> dict[str, Any]:
    if not path.exists():
        return {"schema_version": 1, "deliveries": []}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1 or not isinstance(payload.get("deliveries"), list):
        raise ValueError("deliveries.json 格式无效")
    return payload


def active_delivery(payload: dict[str, Any], courseware_id: str) -> dict[str, Any] | None:
    matches = [
        item
        for item in payload["deliveries"]
        if item.get("courseware_id") == courseware_id
        and item.get("bucket") == BUCKET
        and item.get("active") is True
    ]
    return matches[-1] if matches else None


def deactivate_deliveries(payload: dict[str, Any], courseware_id: str) -> int:
    """Keep history while ensuring a newly appended delivery is the sole active one."""

    changed = 0
    for item in payload["deliveries"]:
        if item.get("courseware_id") == courseware_id and item.get("active") is True:
            item["active"] = False
            changed += 1
    return changed


def random_token() -> str:
    token = secrets.token_urlsafe(36)
    if not TOKEN_RE.fullmatch(token):
        raise RuntimeError("无法生成至少 48 位的密码学随机路径")
    return token


def public_url(bucket: str, region: str, key: str) -> str:
    encoded_key = "/".join(quote(part, safe="") for part in key.split("/"))
    return f"https://{bucket}.oss-{region}.aliyuncs.com/{encoded_key}"


def delete_prefix(api: Any, bucket: str, prefix: str) -> int:
    sdk = require_sdk()
    continuation = None
    deleted = 0
    while True:
        result = api.list_objects_v2(
            sdk.ListObjectsV2Request(
                bucket=bucket,
                prefix=prefix,
                continuation_token=continuation,
            )
        )
        for item in result.contents or []:
            api.delete_object(sdk.DeleteObjectRequest(bucket=bucket, key=item.key))
            deleted += 1
        if not result.is_truncated:
            break
        continuation = result.next_continuation_token
        if not continuation:
            raise RuntimeError("删除旧交付前缀时缺少 continuation token")
    return deleted


def deliver(api: Any, source: Path, bucket: str, region: str, *, rotate: bool) -> str:
    sdk = require_sdk()
    files = courseware_files(source)
    courseware_id = source.resolve().name
    payload = load_deliveries()
    previous = active_delivery(payload, courseware_id)
    if previous and not rotate:
        token = previous.get("token", "")
        if not TOKEN_RE.fullmatch(token):
            raise ValueError("既有交付记录的随机路径无效")
        reused = True
    else:
        token = random_token()
        reused = False
    object_prefix = f"{PREFIX}{token}/{courseware_id}/"

    for path, relative in files:
        key = object_prefix + relative
        result = api.put_object(
            sdk.PutObjectRequest(
                bucket=bucket,
                key=key,
                body=path.read_bytes(),
                content_type=content_type(relative),
                content_disposition="inline",
                cache_control="no-store",
            )
        )
        if not 200 <= result.status_code < 300:
            raise RuntimeError(f"上传失败：{relative}（HTTP {result.status_code}）")

    rotated_deleted = 0
    if previous and rotate:
        old_prefix = previous.get("object_prefix", "")
        if not isinstance(old_prefix, str) or not old_prefix.startswith(PREFIX):
            raise ValueError("既有交付记录的对象前缀无效")
        if old_prefix != object_prefix:
            rotated_deleted = delete_prefix(api, bucket, old_prefix)

    deactivate_deliveries(payload, courseware_id)

    index_key = object_prefix + "index.html"
    url = public_url(bucket, region, index_key)
    record = {
        "delivery_id": secrets.token_hex(8),
        "courseware_id": courseware_id,
        "bucket": bucket,
        "region": region,
        "token": token,
        "object_prefix": object_prefix,
        "url": url,
        "delivered_at": datetime.now(timezone.utc).isoformat(),
        "file_count": len(files),
        "manifest_sha256": manifest_digest(files),
        "reused_path": reused,
        "active": True,
    }
    payload["deliveries"].append(record)
    DELIVERIES_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary = DELIVERIES_FILE.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(DELIVERIES_FILE)
    print(f"delivery_files={len(files)} path={'reused' if reused else 'new'}")
    if rotated_deleted:
        print(f"rotated_old_objects_deleted={rotated_deleted}")
    print(f"delivery_url={url}")
    return url


def safe_error(error: BaseException) -> str:
    if oss is not None:
        service_error = unwrap_service_error(error)
        if service_error:
            return f"OSS {service_error.code}（HTTP {service_error.status_code}）"
    return str(error)


def main() -> int:
    parser = argparse.ArgumentParser(description="私有课件 OSS 长期链接交付")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("inspect")
    subparsers.add_parser("ensure")
    deliver_parser = subparsers.add_parser("deliver")
    deliver_parser.add_argument("source", type=Path)
    deliver_parser.add_argument("--rotate", action="store_true")
    args = parser.parse_args()
    try:
        bucket, region = settings()
        api = client(region)
        if args.command == "inspect":
            inspect_bucket(api, bucket)
        elif args.command == "ensure":
            ensure_bucket(api, bucket, region)
        else:
            ensure_bucket(api, bucket, region)
            deliver(api, args.source, bucket, region, rotate=args.rotate)
    except Exception as error:
        known = isinstance(error, (ValueError, RuntimeError, json.JSONDecodeError))
        sdk_error = bool(oss is not None and isinstance(error, oss.exceptions.BaseError))
        if known or sdk_error:
            print(f"私有交付失败：{safe_error(error)}", file=sys.stderr)
            return 1
        raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
