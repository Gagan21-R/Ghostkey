#!/bin/sh
# Start the FastAPI backend (internal only, supervised) and the Next.js server (public, on $PORT).

echo "[ghostkey] PORT=${PORT:-8080} GHOSTKEY_DB=${GHOSTKEY_DB:-sqlite:///./ghostkey.db} DETECTIF_API_KEY set: $([ -n "$DETECTIF_API_KEY$DETECTIFAI_API_KEY" ] && echo yes || echo NO)"

cd /app/backend
# self-check: fails loudly in the deploy logs if a dependency or the app itself cannot load
python -c "import cv2, numpy, fastapi, sqlalchemy; print('[ghostkey] deps ok: opencv', cv2.__version__, '| numpy', numpy.__version__)" \
  || echo "[ghostkey] ERROR: backend dependencies failed to import (see traceback above)"

# backend supervisor: restart it if it ever exits, and say why in the logs
(
  while true; do
    echo "[ghostkey] starting backend on 127.0.0.1:8000"
    python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
    echo "[ghostkey] backend exited (code $?), restarting in 3 s"
    sleep 3
  done
) &

cd /app/frontend
export HOSTNAME=0.0.0.0
export PORT="${PORT:-8080}"
export BACKEND_URL="${BACKEND_URL:-http://127.0.0.1:8000}"
echo "[ghostkey] starting frontend on 0.0.0.0:${PORT}"
exec node server.js
