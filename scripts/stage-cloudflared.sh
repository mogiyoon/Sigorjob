#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TARGET="$(rustc -vV | awk '/host:/ {print $2}')"
BIN_DIR="$ROOT/src-tauri/binaries"
DEST="$BIN_DIR/cloudflared-${TARGET}"

resolve_source() {
  if [ -n "${CLOUDFLARED_PATH:-}" ] && [ -f "${CLOUDFLARED_PATH}" ]; then
    printf '%s\n' "$CLOUDFLARED_PATH"
    return 0
  fi

  if command -v cloudflared >/dev/null 2>&1; then
    command -v cloudflared
    return 0
  fi

  return 1
}

if ! command -v rustc >/dev/null 2>&1; then
  echo "Missing requirement: rustc"
  exit 1
fi

if ! SRC="$(resolve_source)"; then
  echo "Missing requirement: cloudflared"
  echo "Install cloudflared locally or set CLOUDFLARED_PATH so it can be bundled into the desktop app."
  exit 1
fi

mkdir -p "$BIN_DIR"

if [ -f "$DEST" ] && cmp -s "$SRC" "$DEST"; then
  echo "Bundled cloudflared is already up to date:"
  echo "- source: $SRC"
  echo "- target: $DEST"
  exit 0
fi

rm -f "$DEST"
cp "$SRC" "$DEST"
chmod +x "$DEST"

echo "Staged cloudflared for bundling:"
echo "- source: $SRC"
echo "- target: $DEST"
