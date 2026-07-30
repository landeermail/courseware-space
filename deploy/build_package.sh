#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_DIR="$ROOT/deploy/dist"
WORK_DIR="$(mktemp -d /tmp/courseware-fc-build.XXXXXX)"
PACKAGE_DIR="$WORK_DIR/package"
IMAGE="python:3.11-slim-bookworm"
BUILD_MODE="${COURSEWARE_BUILD_MODE:-auto}"

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

mkdir -p "$DIST_DIR" "$PACKAGE_DIR/server" "$PACKAGE_DIR/generator"

if [[ "$USE_DOCKER" == "true" ]]; then
  if ! docker info >/dev/null 2>&1; then
    printf '已指定 Docker 构建，但 Docker 当前不可用。\n' >&2
    exit 1
  fi
  docker run --rm --platform linux/amd64 \
    --volume "$ROOT:/src:ro" \
    --volume "$PACKAGE_DIR:/out" \
    "$IMAGE" \
    /bin/sh -c 'set -eu
      python3 -m pip install --disable-pip-version-check --no-cache-dir --requirement /src/deploy/requirements.txt --target /out/python >/dev/null'
  printf 'dependency_build=docker-linux-amd64\n'
else
  WHEEL_DIR="$WORK_DIR/wheels"
  mkdir -p "$WHEEL_DIR" "$PACKAGE_DIR/python"
  python3 -m pip download --disable-pip-version-check --no-input --only-binary=:all: \
    --platform manylinux_2_28_x86_64 --platform manylinux2014_x86_64 \
    --implementation cp --python-version 311 --abi cp311 \
    --destination-directory "$WHEEL_DIR" --requirement "$ROOT/deploy/requirements.txt" >/dev/null
  for wheel in "$WHEEL_DIR"/*.whl; do
    python3 -m zipfile -e "$wheel" "$PACKAGE_DIR/python"
  done
  pdfium_library="$(find "$PACKAGE_DIR/python" -type f -name 'libpdfium.so' | sed -n '1p')"
  if [[ -z "$pdfium_library" ]] || ! file "$pdfium_library" | grep -q 'x86-64'; then
    printf 'PDFium manylinux x86_64 动态库校验失败。\n' >&2
    exit 1
  fi
  printf 'dependency_build=manylinux-wheels-x86_64\n'
fi

cp "$ROOT/server/app.py" "$ROOT/server/artifact_store.py" "$ROOT/server/generator_service.py" "$ROOT/server/kimi_client.py" "$ROOT/server/media_service.py" "$ROOT/server/media_demo.html" "$PACKAGE_DIR/server/"
cp "$ROOT/generator/index.html" "$PACKAGE_DIR/generator/index.html"
cp -R "$ROOT/templates" "$PACKAGE_DIR/templates"
cp "$ROOT/deploy/fc/bootstrap" "$PACKAGE_DIR/bootstrap"
chmod 755 "$PACKAGE_DIR/bootstrap"

TEMP_ZIP="$WORK_DIR/courseware-space-fc.zip"
(
  cd "$PACKAGE_DIR"
  zip -q -r "$TEMP_ZIP" .
)
mv "$TEMP_ZIP" "$DIST_DIR/courseware-space-fc.zip"
shasum -a 256 "$DIST_DIR/courseware-space-fc.zip" | sed "s|$ROOT/||"
printf 'package=%s\n' "$DIST_DIR/courseware-space-fc.zip"
