#!/bin/bash
# Python 백엔드를 PyInstaller로 단일 바이너리로 빌드
# 결과물: src-tauri/binaries/backend-{target}

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_DIR="$ROOT/backend"
TAURI_BIN_DIR="$ROOT/src-tauri/binaries"
TARGET="$(rustc -vV | awk '/host:/ {print $2}')"
PYINSTALLER_CONFIG_DIR="${PYINSTALLER_CONFIG_DIR:-$ROOT/.cache/pyinstaller}"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Missing requirement: python3"
  exit 1
fi

if ! command -v rustc >/dev/null 2>&1; then
  echo "Missing requirement: rustc"
  exit 1
fi

if [ ! -f "$BACKEND_DIR/requirements.txt" ]; then
  echo "Missing file: $BACKEND_DIR/requirements.txt"
  exit 1
fi

cd "$BACKEND_DIR"
mkdir -p "$PYINSTALLER_CONFIG_DIR"

echo "=== Installing dependencies ==="
python3 -m pip install -r requirements.txt
if [ -f "$BACKEND_DIR/requirements-optional.txt" ]; then
  if ! python3 -m pip install -r requirements-optional.txt; then
    echo "Optional dependencies could not be installed. Continuing without them."
  fi
fi
python3 -m pip install pyinstaller

echo "=== Building backend binary ==="
PYINSTALLER_CONFIG_DIR="$PYINSTALLER_CONFIG_DIR" python3 -m PyInstaller main.py \
  --onefile \
  --name backend \
  --add-data "policy/policies.yaml:policy" \
  --add-data "intent/rules/rules.yaml:intent/rules" \
  --hidden-import aiosqlite \
  --hidden-import uvicorn.logging \
  --hidden-import uvicorn.loops \
  --hidden-import uvicorn.loops.auto \
  --hidden-import uvicorn.protocols \
  --hidden-import uvicorn.protocols.http \
  --hidden-import uvicorn.protocols.http.auto \
  --hidden-import uvicorn.lifespan \
  --hidden-import uvicorn.lifespan.on

if [ ! -f "$BACKEND_DIR/dist/backend" ]; then
  echo "Backend build failed: dist/backend was not created."
  exit 1
fi

echo "=== Copying to src-tauri/binaries ==="
mkdir -p "$TAURI_BIN_DIR"
cp "$BACKEND_DIR/dist/backend" "$TAURI_BIN_DIR/backend-${TARGET}"
chmod +x "$TAURI_BIN_DIR/backend-${TARGET}"

echo "=== Done: src-tauri/binaries/backend-${TARGET} ==="
