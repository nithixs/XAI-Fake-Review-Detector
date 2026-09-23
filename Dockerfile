FROM node:22-bookworm-slim AS frontend-build
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DB_ENGINE=sqlite \
    SQLITE_PATH=/data/reviewguard.db \
    SEED_DEMO=false \
    SEED_CATALOGUE=true \
    PORT=8000
WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*
COPY requirements-lock.txt ./
RUN python -m pip install -r requirements-lock.txt
COPY backend/ ./backend/
COPY ai_model/saved_model/ ./ai_model/saved_model/
COPY frontend/public/ ./frontend/public/
COPY --from=frontend-build /build/frontend/dist/ ./frontend/dist/
RUN mkdir -p /data
EXPOSE 8000
CMD ["sh", "-c", "exec python -m uvicorn backend.main:app --host 0.0.0.0 --port \"${PORT:-8000}\""]
