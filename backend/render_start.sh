#!/usr/bin/env bash
# Render.com: run API + stream worker in one service (shared SQLite volume).
set -euo pipefail
cd "$(dirname "$0")"

pip install -r requirements.txt

# Render persistent disk mounts at /var/data — SQLite cannot create this path itself.
if [[ "${DATABASE_URL:-}" == *"/var/data/"* ]]; then
  mkdir -p /var/data
  echo "Using SQLite at /var/data (disk mount required on Render)"
fi

python -m worker.stream_worker &
WORKER_PID=$!

cleanup() {
  kill "$WORKER_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
