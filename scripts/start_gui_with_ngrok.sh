#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"
APP_LOG="${APP_LOG:-/tmp/sansan-competition-app.log}"
NGROK_LOG="${NGROK_LOG:-/tmp/sansan-competition-ngrok.log}"
NGROK_LOCAL_API="${NGROK_LOCAL_API:-http://127.0.0.1:4040/api/tunnels}"
NGROK_DOMAIN="${NGROK_DOMAIN:-}"
NGROK_AUTHTOKEN="${NGROK_AUTHTOKEN:-}"

app_pid=""
ngrok_pid=""

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

cleanup() {
  local exit_code=$?
  set +e
  if [[ -n "${ngrok_pid}" ]]; then
    kill "${ngrok_pid}" 2>/dev/null
  fi
  if [[ -n "${app_pid}" ]]; then
    kill "${app_pid}" 2>/dev/null
  fi
  wait "${ngrok_pid}" 2>/dev/null
  wait "${app_pid}" 2>/dev/null
  exit "${exit_code}"
}

trap cleanup EXIT INT TERM

require_command uv
require_command ngrok
require_command curl
require_command python3

if [[ -n "${NGROK_AUTHTOKEN}" ]]; then
  ngrok config add-authtoken "${NGROK_AUTHTOKEN}" >/dev/null
fi

if ! ngrok config check >/dev/null 2>&1; then
  cat >&2 <<'EOF'
ngrok is installed but not authenticated.

Do one of the following:
  1. Set NGROK_AUTHTOKEN for this command
  2. Run: ngrok config add-authtoken <YOUR_TOKEN>

You can find the token in the ngrok dashboard.
EOF
  exit 1
fi

ngrok_args=(http "http://${HOST}:${PORT}" --log stdout --log-format logfmt)
if [[ -n "${NGROK_DOMAIN}" ]]; then
  if [[ "${NGROK_DOMAIN}" == http://* || "${NGROK_DOMAIN}" == https://* ]]; then
    ngrok_url="${NGROK_DOMAIN}"
  else
    ngrok_url="https://${NGROK_DOMAIN}"
  fi
  ngrok_args+=(--url "${ngrok_url}")
fi

: >"${APP_LOG}"
: >"${NGROK_LOG}"

(
  cd "${ROOT_DIR}"
  exec uv run python main.py --host "${HOST}" --port "${PORT}"
) >"${APP_LOG}" 2>&1 &
app_pid=$!

for _ in $(seq 1 50); do
  if curl -fsS "http://${HOST}:${PORT}/api/live/oauth/config" >/dev/null 2>&1; then
    break
  fi
  sleep 0.2
done

if ! curl -fsS "http://${HOST}:${PORT}/api/live/oauth/config" >/dev/null 2>&1; then
  echo "Local GUI failed to start. Check ${APP_LOG}" >&2
  exit 1
fi

ngrok "${ngrok_args[@]}" >"${NGROK_LOG}" 2>&1 &
ngrok_pid=$!

public_url=""
for _ in $(seq 1 50); do
  public_url="$(
    curl -fsS "${NGROK_LOCAL_API}" 2>/dev/null | python3 - <<'PY'
import json
import sys

try:
    payload = json.load(sys.stdin)
except Exception:
    print("")
    raise SystemExit(0)

for tunnel in payload.get("tunnels", []):
    url = str(tunnel.get("public_url") or "").strip()
    if url.startswith("https://"):
        print(url)
        raise SystemExit(0)

print("")
PY
  )"
  if [[ -n "${public_url}" ]]; then
    break
  fi
  sleep 0.2
done

if [[ -z "${public_url}" ]]; then
  echo "ngrok tunnel failed to start. Check ${NGROK_LOG}" >&2
  exit 1
fi

redirect_uri="${public_url}/oauth/google/callback"

cat <<EOF
sansan-competition local GUI is running.

Local URL:
  http://${HOST}:${PORT}

ngrok URL:
  ${public_url}

Google OAuth redirect URI:
  ${redirect_uri}

Next steps:
  1. Add the redirect URI to your Google OAuth Web application client.
  2. Re-download the OAuth client JSON.
  3. Open ${public_url} and upload that JSON from the login screen.

Logs:
  app   -> ${APP_LOG}
  ngrok -> ${NGROK_LOG}

Press Ctrl+C to stop both processes.
EOF

tail -f "${APP_LOG}" "${NGROK_LOG}"
