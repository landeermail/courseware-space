#!/usr/bin/env bash
# Build the feedback-only FC package: whitelist sources + OSS SDK only.
# The post-build audit fails the build if the zip contains any generator,
# media, templates, or Kimi reference. --audit-only re-runs that audit on an
# existing zip (used by offline tests and security review).
set -euo pipefail

MODULE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$MODULE_ROOT/../.." && pwd)"
DIST_DIR="$MODULE_ROOT/dist"
PACKAGE_NAME="courseware-space-feedback-fc.zip"
IMAGE="python:3.11-slim-bookworm"
BUILD_MODE="${COURSEWARE_BUILD_MODE:-auto}"

audit_zip() {
  local zip_path="$1"
  if [[ ! -f "$zip_path" ]]; then
    printf '部署包不存在：%s\n' "$zip_path" >&2
    return 1
  fi
  local listing forbidden_names
  listing="$(zipinfo -1 "$zip_path")"
  forbidden_names="$(printf '%s\n' "$listing" | grep -iE 'kimi|generator|media|templates' || true)"
  if [[ -n "$forbidden_names" ]]; then
    printf '部署包含禁用文件：\n%s\n' "$forbidden_names" >&2
    return 1
  fi
  local kimi_refs
  kimi_refs="$(grep -aic 'kimi' < <(unzip -p "$zip_path" 2>/dev/null || true) || true)"
  if [[ "$kimi_refs" != "0" ]]; then
    printf '部署包内容出现 kimi 引用（%s 处）。\n' "$kimi_refs" >&2
    return 1
  fi
  if unzip -p "$zip_path" 2>/dev/null | grep -aq 'KIMI_API_KEY'; then
    printf '部署包内容出现 KIMI_API_KEY。\n' >&2
    return 1
  fi
  local required missing unexpected
  required='bootstrap
services/__init__.py
services/feedback/__init__.py
services/feedback/access_control.py
services/feedback/app.py
services/feedback/review_workspace.py
services/feedback/schema/__init__.py
services/feedback/schema/validate_feedback.py
services/feedback/service.py'
  missing="$(comm -23 <(printf '%s\n' "$required" | sort) <(printf '%s\n' "$listing" | sort) || true)"
  if [[ -n "$missing" ]]; then
    printf '部署包缺少必需文件：\n%s\n' "$missing" >&2
    return 1
  fi
  unexpected="$(printf '%s\n' "$listing" | grep -vE '^(bootstrap|services/__init__\.py|services/feedback/(__init__|access_control|app|review_workspace|service)\.py|services/feedback/schema/(__init__|validate_feedback)\.py|python/.*|services/?|services/feedback/?|services/feedback/schema/?)$' || true)"
  if [[ -n "$unexpected" ]]; then
    printf '部署包含白名单外文件：\n%s\n' "$unexpected" >&2
    return 1
  fi
  printf 'package_audit=required_files=9 unexpected_files=0 forbidden_names=0 kimi_refs=0\n'
}

if [[ "${1:-}" == "--audit-only" ]]; then
  audit_zip "${2:?"--audit-only 需要提供 zip 路径"}"
  exit $?
fi

case "$BUILD_MODE" in
  auto|docker|wheels) ;;
  *)
    printf 'COURSEWARE_BUILD_MODE 仅支持 auto、docker 或 wheels。\n' >&2
    exit 1
    ;;
esac

USE_DOCKER=false
if [[ "$BUILD_MODE" == "docker" ]]; then
  USE_DOCKER=true
elif [[ "$BUILD_MODE" == "auto" ]] && [[ "$(uname -m)" == "x86_64" ]] && docker info >/dev/null 2>&1; then
  USE_DOCKER=true
fi

WORK_DIR="$(mktemp -d /tmp/courseware-feedback-fc-build.XXXXXX)"
PACKAGE_DIR="$WORK_DIR/package"
mkdir -p "$DIST_DIR" "$PACKAGE_DIR/services/feedback/schema"

if [[ "$USE_DOCKER" == "true" ]]; then
  if ! docker info >/dev/null 2>&1; then
    printf '已指定 Docker 构建，但 Docker 当前不可用。\n' >&2
    exit 1
  fi
  docker run --rm --platform linux/amd64 \
    --volume "$REPO_ROOT:/src:ro" \
    --volume "$PACKAGE_DIR:/out" \
    "$IMAGE" \
    /bin/sh -c 'set -eu
      python3 -m pip install --disable-pip-version-check --no-cache-dir --requirement /src/services/feedback/deploy/requirements.txt --target /out/python >/dev/null'
  printf 'dependency_build=docker-linux-amd64\n'
else
  WHEEL_DIR="$WORK_DIR/wheels"
  mkdir -p "$WHEEL_DIR" "$PACKAGE_DIR/python"
  python3 -m pip download --disable-pip-version-check --no-input --only-binary=:all: \
    --platform manylinux_2_28_x86_64 --platform manylinux2014_x86_64 \
    --implementation cp --python-version 311 --abi cp311 \
    --destination-directory "$WHEEL_DIR" --requirement "$MODULE_ROOT/deploy/requirements.txt" >/dev/null
  for wheel in "$WHEEL_DIR"/*.whl; do
    python3 -m zipfile -e "$wheel" "$PACKAGE_DIR/python"
  done
  printf 'dependency_build=manylinux-wheels-x86_64\n'
fi

# 白名单复制：只包含 feedback 模块运行时、校验器与 bootstrap。
cp "$REPO_ROOT/services/__init__.py" "$PACKAGE_DIR/services/__init__.py"
cp "$MODULE_ROOT/__init__.py" "$MODULE_ROOT/app.py" "$MODULE_ROOT/access_control.py" \
  "$MODULE_ROOT/service.py" "$MODULE_ROOT/review_workspace.py" "$PACKAGE_DIR/services/feedback/"
cp "$MODULE_ROOT/schema/__init__.py" "$MODULE_ROOT/schema/validate_feedback.py" \
  "$PACKAGE_DIR/services/feedback/schema/"
cp "$MODULE_ROOT/deploy/bootstrap" "$PACKAGE_DIR/bootstrap"
chmod 755 "$PACKAGE_DIR/bootstrap"

TEMP_ZIP="$WORK_DIR/$PACKAGE_NAME"
(
  cd "$PACKAGE_DIR"
  zip -q -r "$TEMP_ZIP" .
)

audit_zip "$TEMP_ZIP"
mv "$TEMP_ZIP" "$DIST_DIR/$PACKAGE_NAME"
shasum -a 256 "$DIST_DIR/$PACKAGE_NAME" | sed "s|$REPO_ROOT/||"
printf 'package=%s\n' "$DIST_DIR/$PACKAGE_NAME"
