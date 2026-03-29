#!/bin/bash

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TARGET="$(rustc -vV | awk '/host:/ {print $2}')"
CHECK_REMOTE=0
BUNDLED_CLOUDFLARED="$ROOT/src-tauri/binaries/cloudflared-${TARGET}"

if [ "${1:-}" = "--with-remote" ]; then
  CHECK_REMOTE=1
fi

echo "=== Distribution readiness check ==="
echo "Target triple: $TARGET"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Missing requirement: python3"
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "Missing requirement: npm"
  exit 1
fi

if ! command -v cargo >/dev/null 2>&1; then
  echo "Missing requirement: cargo"
  exit 1
fi

if [ "$CHECK_REMOTE" -eq 1 ]; then
  if [ -f "$BUNDLED_CLOUDFLARED" ]; then
    echo "Remote/mobile bundle asset found: $BUNDLED_CLOUDFLARED"
  elif command -v cloudflared >/dev/null 2>&1 || [ -n "${CLOUDFLARED_PATH:-}" ]; then
    echo "Remote/mobile bundling source is available and can be staged during build."
  else
    echo "Missing cloudflared for remote/mobile packaging."
    echo "Install cloudflared locally or set CLOUDFLARED_PATH before building the desktop app."
    exit 1
  fi
fi

echo "Ready to build distributable artifacts for local usage."

if [ "$CHECK_REMOTE" -eq 1 ]; then
  echo "Remote/mobile tunnel checks passed."
else
  echo "Remote/mobile tunnel check skipped. Use --with-remote to validate cloudflared too."
fi
