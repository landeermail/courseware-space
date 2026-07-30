#!/usr/bin/env bash
set -euo pipefail

REGION="${COURSEWARE_OSS_REGION:-cn-hangzhou}"
BUCKET="${COURSEWARE_OSS_BUCKET:-}"
FUNCTION="${COURSEWARE_FC_FUNCTION:-courseware-space-generator}"
CODE_OBJECT="${COURSEWARE_FC_CODE_OBJECT:-}"
CLI="${ALIYUN_CLI:-$(command -v aliyun || printf '')}"

if [[ -z "${ALIBABA_CLOUD_ACCESS_KEY_ID:-}" || -z "${ALIBABA_CLOUD_ACCESS_KEY_SECRET:-}" ]]; then
  printf '回滚需要临时注入阿里云部署凭证。\n' >&2
  exit 1
fi
if [[ "$BUCKET" != courseware-space-* || "$FUNCTION" != courseware-space-* ]]; then
  printf 'bucket/function 必须使用 courseware-space-* 前缀。\n' >&2
  exit 1
fi
if [[ ! "$CODE_OBJECT" =~ ^deploy/code/[a-f0-9]{64}\.zip$ ]]; then
  printf 'COURSEWARE_FC_CODE_OBJECT 必须是已知的内容寻址 deploy/code/<sha256>.zip。\n' >&2
  exit 1
fi
if [[ -z "$CLI" || ! -x "$CLI" ]]; then
  printf '未找到阿里云 CLI。\n' >&2
  exit 1
fi

export ALIBABA_CLOUD_IGNORE_PROFILE=TRUE
"$CLI" fc update-function --region "$REGION" --function-name "$FUNCTION" \
  --code "ossBucketName=$BUCKET" "ossObjectName=$CODE_OBJECT" >/dev/null
printf 'rollback_code=%s\nrollback_status=ok\n' "$CODE_OBJECT"
