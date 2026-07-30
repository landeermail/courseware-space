#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

read_secret() {
  security find-generic-password -a "$USER" -s "$1" -w
}

export ALIBABA_CLOUD_ACCESS_KEY_ID="$(read_secret courseware-space-aliyun-access-key-id)"
export ALIBABA_CLOUD_ACCESS_KEY_SECRET="$(read_secret courseware-space-aliyun-access-key-secret)"
export KIMI_API_KEY="$(read_secret courseware-space-kimi)"
export COURSEWARE_ACCESS_CODE="$(read_secret courseware-space-preview-access-code)"
export COURSEWARE_OSS_BUCKET="${COURSEWARE_OSS_BUCKET:-courseware-space-demo-10794778}"
export COURSEWARE_FEEDBACK_OSS_BUCKET="${COURSEWARE_FEEDBACK_OSS_BUCKET:-courseware-space-private-10794778}"

exec "$ROOT/deploy/deploy.sh"
