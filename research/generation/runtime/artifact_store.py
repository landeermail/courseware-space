"""Publish generated courseware locally or to a narrowly scoped OSS prefix."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Protocol


JOB_ID_PATTERN = re.compile(r"^[a-f0-9]{12}$")


class ArtifactStoreError(RuntimeError):
    pass


class ArtifactStore(Protocol):
    backend: str

    def publish(self, job_id: str, output_dir: Path) -> str:
        ...


class LocalArtifactStore:
    backend = "local"

    def publish(self, job_id: str, output_dir: Path) -> str:
        if not JOB_ID_PATTERN.fullmatch(job_id) or not (output_dir / "index.html").is_file():
            raise ArtifactStoreError("本地产物不完整")
        return f"/generated/{job_id}/"


class OssArtifactStore:
    backend = "oss"

    def __init__(self, bucket: str, region: str, endpoint: str | None = None) -> None:
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,61}[a-z0-9]", bucket):
            raise ArtifactStoreError("COURSEWARE_OSS_BUCKET 格式无效")
        if not re.fullmatch(r"cn-[a-z0-9-]+", region):
            raise ArtifactStoreError("COURSEWARE_OSS_REGION 格式无效")
        try:
            import alibabacloud_oss_v2 as oss
        except ImportError as error:
            raise ArtifactStoreError("云端产物存储缺少 alibabacloud-oss-v2") from error
        self.oss = oss
        self.bucket = bucket
        self.region = region
        self.public_base = f"https://{bucket}.oss-{region}.aliyuncs.com"
        provider = oss.credentials.EnvironmentVariableCredentialsProvider()
        config = oss.config.load_default()
        config.credentials_provider = provider
        config.region = region
        config.endpoint = endpoint or f"https://oss-{region}-internal.aliyuncs.com"
        self.client = oss.Client(config)

    def publish(self, job_id: str, output_dir: Path) -> str:
        if not JOB_ID_PATTERN.fullmatch(job_id):
            raise ArtifactStoreError("OSS job id 无效")
        index_path = output_dir / "index.html"
        metadata_path = output_dir / "metadata.json"
        if not index_path.is_file() or not metadata_path.is_file():
            raise ArtifactStoreError("OSS 产物必须同时包含 index.html 与 metadata.json")
        prefix = f"staging/{job_id}"
        uploads = [
            (metadata_path, f"{prefix}/metadata.json", "application/json; charset=utf-8", "no-store"),
            (index_path, f"{prefix}/index.html", "text/html; charset=utf-8", "public, max-age=300"),
        ]
        try:
            for source, key, content_type, cache_control in uploads:
                result = self.client.put_object(
                    self.oss.PutObjectRequest(
                        bucket=self.bucket,
                        key=key,
                        body=source.read_bytes(),
                        acl="public-read",
                        content_type=content_type,
                        cache_control=cache_control,
                        forbid_overwrite=True,
                    )
                )
                if not 200 <= result.status_code < 300:
                    raise ArtifactStoreError(f"OSS 上传失败（HTTP {result.status_code}）")
        except ArtifactStoreError:
            raise
        except Exception as error:
            raise ArtifactStoreError(f"OSS 上传失败：{type(error).__name__}") from error
        return f"{self.public_base}/{prefix}/index.html"


def artifact_store_from_environment() -> ArtifactStore:
    bucket = os.environ.get("COURSEWARE_OSS_BUCKET", "").strip()
    if not bucket:
        return LocalArtifactStore()
    region = os.environ.get("COURSEWARE_OSS_REGION", "cn-hangzhou").strip()
    endpoint = os.environ.get("COURSEWARE_OSS_ENDPOINT", "").strip() or None
    return OssArtifactStore(bucket, region, endpoint)
