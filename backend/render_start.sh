#!/usr/bin/env bash
# Render.com: run API + stream worker in one service (shared SQLite volume).
set -euo pipefail
cd "$(dirname "$0")"

pip install -r requirements.txt

# /var/data only exists when a Render persistent disk is mounted there — never mkdir it.
if [[ "${DATABASE_URL:-}" == *"/var/data/"* ]]; then
  if [[ -d /var/data ]] && [[ -w /var/data ]]; then
    echo "SQLite on Render persistent disk: ${DATABASE_URL}"
  else
    echo "WARN: No writable disk at /var/data — using ./podium.db"
    echo "      Add a Render disk (mount path /var/data) to persist data across deploys."
    export DATABASE_URL="sqlite:///./podium.db"
  fi
fi

python -m worker.stream_worker &
WORKER_PID=$!

cleanup() {
  kill "$WORKER_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
