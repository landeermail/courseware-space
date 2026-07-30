#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROTATE_FLAG=""
if [[ "${1:-}" == "--rotate" ]]; then
  ROTATE_FLAG="--rotate"
  shift
fi
if [[ "$#" -ne 1 ]]; then
  printf '用法：%s [--rotate] trial/private/courseware/<课件目录>\n' "$0" >&2
  exit 2
fi

if [[ -n "$ROTATE_FLAG" ]]; then
  exec "$ROOT/deploy/private_cloud.sh" deliver "$1" "$ROTATE_FLAG"
fi
exec "$ROOT/deploy/private_cloud.sh" deliver "$1"
