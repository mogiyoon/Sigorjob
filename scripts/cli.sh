#!/bin/bash
# Headless CLI entrypoint for the Agent Platform backend

set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

cd "$ROOT/backend"
python main.py "$@"
