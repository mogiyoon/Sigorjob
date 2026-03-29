#!/bin/bash

set -euo pipefail

BASE_URL="${1:-http://127.0.0.1:8000}"

if ! command -v curl >/dev/null 2>&1; then
  echo "Missing requirement: curl"
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "Missing requirement: python3"
  exit 1
fi

fetch_json() {
  local path="$1"
  curl --silent --show-error --fail "${BASE_URL}${path}"
}

read_json_field() {
  local field="$1"
  python3 -c 'import json, sys; data=json.load(sys.stdin); value=data.get(sys.argv[1]); print("" if value is None else value)' "$field"
}

echo "=== Remote access readiness ==="
echo "Base URL: $BASE_URL"

if ! setup_json="$(fetch_json "/setup/status")"; then
  echo "Could not reach the local setup API."
  echo "Make sure the backend is running and accessible at $BASE_URL."
  exit 1
fi

pair_json="$(fetch_json "/pair/data" || true)"

cloudflared_installed="$(printf '%s' "$setup_json" | read_json_field "cloudflared_installed")"
configured="$(printf '%s' "$setup_json" | read_json_field "configured")"
tunnel_active="$(printf '%s' "$setup_json" | read_json_field "tunnel_active")"
tunnel_url="$(printf '%s' "$setup_json" | read_json_field "tunnel_url")"
tunnel_error="$(printf '%s' "$setup_json" | read_json_field "tunnel_error")"

echo
echo "Setup status:"
echo "- cloudflared installed: ${cloudflared_installed:-unknown}"
echo "- Cloudflare token configured: ${configured:-unknown}"
echo "- tunnel active: ${tunnel_active:-unknown}"

if [ -n "${tunnel_url:-}" ]; then
  echo "- tunnel URL: $tunnel_url"
fi

if [ -n "${tunnel_error:-}" ]; then
  echo "- tunnel error: $tunnel_error"
fi

if [ -n "${pair_json:-}" ]; then
  pair_status="$(printf '%s' "$pair_json" | read_json_field "status")"
  echo
  echo "Pairing status:"
  echo "- status: ${pair_status:-unknown}"

  pair_error="$(printf '%s' "$pair_json" | read_json_field "error")"
  if [ -n "${pair_error:-}" ]; then
    echo "- error: $pair_error"
  fi
fi

echo
echo "Next step summary:"
if [ "${cloudflared_installed:-}" != "True" ] && [ "${cloudflared_installed:-}" != "true" ]; then
  echo "- Install cloudflared on the host machine or set CLOUDFLARED_PATH."
  exit 0
fi

if [ "${configured:-}" != "True" ] && [ "${configured:-}" != "true" ]; then
  echo "- Open the local setup page and provide a Cloudflare tunnel token."
  exit 0
fi

if [ "${tunnel_active:-}" != "True" ] && [ "${tunnel_active:-}" != "true" ]; then
  echo "- The tunnel is configured but not active yet. Recheck the token and local network."
  exit 0
fi

echo "- Remote access looks ready. Open the local pairing page and connect the mobile app."
