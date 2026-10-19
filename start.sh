#!/bin/sh
# Start the FastAPI backend (internal only) and the Next.js server (public, on $PORT).
set -e
cd /app/backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 &
cd /app/frontend
export HOSTNAME=0.0.0.0
export PORT="${PORT:-8080}"
export BACKEND_URL="${BACKEND_URL:-http://127.0.0.1:8000}"
exec node server.js
