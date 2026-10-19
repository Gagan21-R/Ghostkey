# GHOSTKEY 2.0: one container, one public URL.
#   Next.js (frontend + server-side API proxy) listens on $PORT (set by Railway / Render / etc.)
#   FastAPI (backend) listens on 127.0.0.1:8000 inside the container and is never exposed directly.
# Secrets come from the platform's environment variables (never baked into the image).

# ---------- 1. build the Next.js frontend (standalone output) ----------
FROM node:22-slim AS web
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
ENV NEXT_DIST_DIR=.next NEXT_OUTPUT=standalone NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# ---------- 2. runtime: Python backend + Node frontend ----------
FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 \
    GHOSTKEY_PUBLIC=1 GHOSTKEY_LOCAL_DOWNLOADS=0
RUN apt-get update && apt-get install -y --no-install-recommends libglib2.0-0 libgomp1 libstdc++6 ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY --from=web /usr/local/bin/node /usr/local/bin/node

WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/ backend/
COPY --from=web /app/frontend/.next/standalone/ frontend/
COPY --from=web /app/frontend/.next/static frontend/.next/static
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh && mkdir -p /data

EXPOSE 8080
CMD ["/app/start.sh"]
