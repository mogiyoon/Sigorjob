#!/bin/bash
# 개발 환경 실행: backend + frontend 동시 시작

set -e
ROOT="$(dirname "$0")/.."

echo "=== Starting backend (localhost:8000) ==="
cd "$ROOT/backend"
pip install -r requirements.txt -q
python main.py &
BACKEND_PID=$!

echo "=== Starting frontend (localhost:3000) ==="
cd "$ROOT/frontend"
npm install -q
npm run dev &
FRONTEND_PID=$!

echo "Backend PID: $BACKEND_PID"
echo "Frontend PID: $FRONTEND_PID"
echo ""
echo "Press Ctrl+C to stop both servers"

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait
