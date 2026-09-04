#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="$ROOT/.venv/bin/python"
WEB_ROOT="$ROOT/web"
STATE_DIR="$ROOT/.webapp"
BACKEND_OUTPUT_LOG="$STATE_DIR/backend-output.log"
BACKEND_ERROR_LOG="$STATE_DIR/backend-error.log"
FRONTEND_OUTPUT_LOG="$STATE_DIR/frontend-output.log"
FRONTEND_ERROR_LOG="$STATE_DIR/frontend-error.log"

if [[ ! -x "$PYTHON" ]]; then
  printf 'Python environment not found: %s\n' "$PYTHON" >&2
  printf 'Run: python3.13 scripts/prepare_env.py\n' >&2
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  printf 'Node.js/npm not found. Install Node.js 22.13+ first.\n' >&2
  exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
  printf 'curl not found. Install curl before starting the app.\n' >&2
  exit 1
fi

mkdir -p "$STATE_DIR"

backend_ready() {
  curl -fsS --max-time 2 http://127.0.0.1:18765/api/health >/dev/null 2>&1
}

frontend_ready() {
  curl -fsS --max-time 2 http://127.0.0.1:13000 >/dev/null 2>&1
}

if ! backend_ready; then
  : > "$BACKEND_OUTPUT_LOG"
  : > "$BACKEND_ERROR_LOG"
  (cd "$ROOT" && nohup "$PYTHON" -m uvicorn webapp.server:app --host 127.0.0.1 --port 18765 >"$BACKEND_OUTPUT_LOG" 2>"$BACKEND_ERROR_LOG" & echo $! > "$STATE_DIR/backend.pid")
fi

if ! frontend_ready; then
  : > "$FRONTEND_OUTPUT_LOG"
  : > "$FRONTEND_ERROR_LOG"
  (cd "$WEB_ROOT" && nohup npm run dev >"$FRONTEND_OUTPUT_LOG" 2>"$FRONTEND_ERROR_LOG" & echo $! > "$STATE_DIR/frontend.pid")
fi

backend_ok=false
frontend_ok=false
for _ in {1..90}; do
  backend_ready && backend_ok=true
  frontend_ready && frontend_ok=true
  if [[ "$backend_ok" == true && "$frontend_ok" == true ]]; then
    break
  fi
  sleep 1
done

if [[ "$backend_ok" != true ]]; then
  printf 'Backend failed to start. See %s\n' "$BACKEND_ERROR_LOG" >&2
  exit 1
fi

if [[ "$frontend_ok" != true ]]; then
  printf 'Frontend failed to start. See %s\n' "$FRONTEND_ERROR_LOG" >&2
  exit 1
fi

printf 'Ready: http://127.0.0.1:13000\n'
if command -v open >/dev/null 2>&1; then
  open http://127.0.0.1:13000 >/dev/null 2>&1 || true
fi
