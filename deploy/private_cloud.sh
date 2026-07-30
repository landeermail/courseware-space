#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SDK_DIR="${TMPDIR:-/tmp}/courseware-private-delivery-sdk-v1-$USER"
umask 077

if [[ "$(uname -s)" != "Darwin" ]] || ! command -v security >/dev/null 2>&1; then
  printf '私有交付当前要求在已配置 macOS 钥匙串的维护电脑上运行。\n' >&2
  exit 1
fi

mkdir -p "$SDK_DIR"
chmod 700 "$SDK_DIR"
if ! PYTHONWARNINGS=ignore PYTHONPATH="$SDK_DIR" python3 -c 'import alibabacloud_oss_v2' >/dev/null 2>&1; then
  python3 -m pip install --disable-pip-version-check --no-input --quiet \
    --target "$SDK_DIR" 'alibabacloud-oss-v2==1.3.2'
fi

export ALIBABA_CLOUD_ACCESS_KEY_ID="$(security find-generic-password -a "$USER" -s courseware-space-aliyun-access-key-id -w)"
export ALIBABA_CLOUD_ACCESS_KEY_SECRET="$(security find-generic-password -a "$USER" -s courseware-space-aliyun-access-key-secret -w)"
export OSS_ACCESS_KEY_ID="$ALIBABA_CLOUD_ACCESS_KEY_ID"
export OSS_ACCESS_KEY_SECRET="$ALIBABA_CLOUD_ACCESS_KEY_SECRET"
export ALIBABA_CLOUD_IGNORE_PROFILE=TRUE
export PYTHONWARNINGS=ignore

exec env PYTHONPATH="$SDK_DIR:$ROOT" python3 "$ROOT/deploy/private_delivery.py" "$@"
