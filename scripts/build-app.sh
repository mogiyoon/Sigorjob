#!/bin/bash
# 전체 앱 빌드: frontend → backend → tauri
# 기본 결과물: src-tauri/target/release/bundle/

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TARGET="$(rustc -vV | awk '/host:/ {print $2}')"
BACKEND_BIN="$ROOT/src-tauri/binaries/backend-${TARGET}"
FRONTEND_DIST="$ROOT/frontend/out/index.html"
BUNDLE_ARGS=(--bundles app)

if [ "${1:-}" = "--with-dmg" ]; then
  BUNDLE_ARGS=(--bundles app,dmg)
fi

if ! command -v rustc >/dev/null 2>&1; then
  echo "Missing requirement: rustc"
  exit 1
fi

if ! command -v npx >/dev/null 2>&1; then
  echo "Missing requirement: npx"
  exit 1
fi

echo "=== [0/3] Check distribution readiness ==="
bash "$ROOT/scripts/check-dist-readiness.sh" --with-remote

echo "=== [1/3] Build Next.js frontend ==="
cd "$ROOT/frontend"
npm install
npm run build  # next.config.js에서 output: "export" 활성화 필요

if [ ! -f "$FRONTEND_DIST" ]; then
  echo "Frontend export is missing: $FRONTEND_DIST"
  exit 1
fi

echo "=== [2/3] Build Python backend ==="
cd "$ROOT"
bash "$ROOT/scripts/build-backend.sh"

if [ ! -f "$BACKEND_BIN" ]; then
  echo "Backend sidecar not found after build: $BACKEND_BIN"
  exit 1
fi

echo "=== [2.5/3] Stage bundled cloudflared ==="
bash "$ROOT/scripts/stage-cloudflared.sh"

echo "=== [3/3] Build Tauri app ==="
cd "$ROOT"
if ! npx tauri --version >/dev/null 2>&1; then
  echo "Tauri CLI is not available through npx."
  echo "Install it with 'npm install -g @tauri-apps/cli' or make it available in your workspace."
  exit 1
fi
npx tauri build "${BUNDLE_ARGS[@]}"

echo "=== Build complete ==="
echo "Output: src-tauri/target/release/bundle/"
echo "Note: packaged desktop builds now bundle cloudflared for end users."
if [ "${1:-}" != "--with-dmg" ]; then
  echo "Note: DMG packaging is skipped by default. Use --with-dmg when you specifically want a macOS disk image."
fi
