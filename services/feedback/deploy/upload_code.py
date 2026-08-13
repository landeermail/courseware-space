#!/usr/bin/env python3
"""Upload a feedback FC package to the existing private code bucket."""

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import re
import sys

import alibabacloud_oss_v2 as oss


def settings() -> tuple[str, str]:
    bucket = os.environ.get("COURSEWARE_OSS_BUCKET", "").strip()
    region = os.environ.get("COURSEWARE_OSS_REGION", "cn-hangzhou").strip()
    if not bucket.startswith("courseware-space-") or not re.fullmatch(
        r"[a-z0-9][a-z0-9-]{1,61}[a-z0-9]", bucket
    ):
        raise ValueError("COURSEWARE_OSS_BUCKET 必须是合法的 courseware-space-* 名称")
    if not re.fullmatch(r"cn-[a-z0-9-]+", region):
        raise ValueError("COURSEWARE_OSS_REGION 无效")
    return bucket, region


def upload(package: Path) -> None:
    if not package.is_file() or package.suffix != ".zip":
        raise ValueError("FC 部署包不存在或不是 zip")
    bucket, region = settings()
    body = package.read_bytes()
    digest = hashlib.sha256(body).hexdigest()
    config = oss.config.load_default()
    config.credentials_provider = oss.credentials.EnvironmentVariableCredentialsProvider()
    config.region = region
    config.endpoint = f"https://oss-{region}.aliyuncs.com"
    result = oss.Client(config).put_object(
        oss.PutObjectRequest(
            bucket=bucket,
            key=f"deploy/code/{digest}.zip",
            body=body,
            acl="private",
            content_type="application/zip",
            cache_control="no-store",
        )
    )
    if not 200 <= result.status_code < 300:
        raise RuntimeError(f"上传 FC 部署包失败（HTTP {result.status_code}）")
    print(f"fc_code_uploaded=sha256:{digest}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True, type=Path)
    args = parser.parse_args()
    try:
        upload(args.package)
    except (ValueError, RuntimeError, OSError, oss.exceptions.BaseError) as error:
        print(f"OSS 部署失败：{error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
