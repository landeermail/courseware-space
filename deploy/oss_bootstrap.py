#!/usr/bin/env python3
"""Create and verify the one task-scoped OSS bucket, then upload FC code."""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
from pathlib import Path

import alibabacloud_oss_v2 as oss


def settings() -> tuple[str, str]:
    bucket = os.environ.get("COURSEWARE_OSS_BUCKET", "").strip()
    region = os.environ.get("COURSEWARE_OSS_REGION", "cn-hangzhou").strip()
    if not bucket.startswith("courseware-space-") or not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,61}[a-z0-9]", bucket):
        raise ValueError("COURSEWARE_OSS_BUCKET 必须是合法的 courseware-space-* 名称")
    if not re.fullmatch(r"cn-[a-z0-9-]+", region):
        raise ValueError("COURSEWARE_OSS_REGION 无效")
    return bucket, region


def client(region: str) -> oss.Client:
    config = oss.config.load_default()
    config.credentials_provider = oss.credentials.EnvironmentVariableCredentialsProvider()
    config.region = region
    config.endpoint = f"https://oss-{region}.aliyuncs.com"
    return oss.Client(config)


def unwrap_service_error(error: BaseException) -> oss.exceptions.ServiceError | None:
    current: BaseException = error
    while isinstance(current, oss.exceptions.OperationError):
        nested = current.unwrap()
        if not isinstance(nested, BaseException):
            return None
        current = nested
    return current if isinstance(current, oss.exceptions.ServiceError) else None


def is_missing(error: BaseException) -> bool:
    service_error = unwrap_service_error(error)
    return bool(
        service_error
        and (
            service_error.status_code == 404
            or service_error.code in {"NoSuchBucket", "NoSuchPublicAccessBlockConfiguration"}
        )
    )


def ensure_bucket(api: oss.Client, bucket: str) -> None:
    created = False
    try:
        api.get_bucket_info(oss.GetBucketInfoRequest(bucket=bucket))
    except oss.exceptions.BaseError as error:
        if not is_missing(error):
            raise
        result = api.put_bucket(
            oss.PutBucketRequest(
                bucket=bucket,
                acl="private",
                create_bucket_configuration=oss.CreateBucketConfiguration(
                    storage_class="Standard",
                    data_redundancy_type="LRS",
                ),
            )
        )
        if not 200 <= result.status_code < 300:
            raise RuntimeError(f"创建 OSS bucket 失败（HTTP {result.status_code}）")
        created = True
        print(f"oss_bucket_created={bucket}")

    acl = api.get_bucket_acl(oss.GetBucketAclRequest(bucket=bucket)).acl
    if acl != "private":
        raise RuntimeError(f"现有 bucket ACL 不是 private（实际 {acl}），为避免修改既有权限已停止")

    if created:
        api.put_bucket_public_access_block(
            oss.PutBucketPublicAccessBlockRequest(
                bucket=bucket,
                public_access_block_configuration=oss.PublicAccessBlockConfiguration(block_public_access=False),
            )
        )
    try:
        public_block = api.get_bucket_public_access_block(
            oss.GetBucketPublicAccessBlockRequest(bucket=bucket)
        ).public_access_block_configuration
        block_enabled = bool(public_block and public_block.block_public_access)
    except oss.exceptions.BaseError as error:
        if not is_missing(error):
            raise
        block_enabled = False
    if block_enabled:
        raise RuntimeError("bucket 仍阻止对象级 public-read，且脚本不会擅自修改既有权限")
    print(f"oss_bucket_verified={bucket} acl=private public_access_block=false")


def inspect_bucket(api: oss.Client, bucket: str) -> None:
    try:
        api.get_bucket_info(oss.GetBucketInfoRequest(bucket=bucket))
    except oss.exceptions.BaseError as error:
        if is_missing(error):
            print("oss_bucket=missing")
            return
        raise
    print("oss_bucket=existing")


def upload_code(api: oss.Client, bucket: str, package: Path) -> None:
    if not package.is_file() or package.suffix != ".zip":
        raise ValueError("FC 部署包不存在或不是 zip")
    digest = hashlib.sha256(package.read_bytes()).hexdigest()
    key = f"deploy/code/{digest}.zip"
    result = api.put_object(
        oss.PutObjectRequest(
            bucket=bucket,
            key=key,
            body=package.read_bytes(),
            acl="private",
            content_type="application/zip",
            cache_control="no-store",
        )
    )
    if not 200 <= result.status_code < 300:
        raise RuntimeError(f"上传 FC 部署包失败（HTTP {result.status_code}）")
    print(f"fc_code_uploaded=oss://{bucket}/{key}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("inspect", "ensure", "upload-code", "verify"))
    parser.add_argument("--package", type=Path)
    args = parser.parse_args()
    try:
        bucket, region = settings()
        api = client(region)
        if args.command == "inspect":
            inspect_bucket(api, bucket)
        if args.command in {"ensure", "verify"}:
            ensure_bucket(api, bucket)
        if args.command == "upload-code":
            if args.package is None:
                raise ValueError("upload-code 必须提供 --package")
            upload_code(api, bucket, args.package)
    except (ValueError, RuntimeError, oss.exceptions.BaseError) as error:
        print(f"OSS 部署失败：{error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
