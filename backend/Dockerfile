# Production FastAPI image — uvicorn ASGI, no reload.
# Dev compose still uses this image with an overridden command when needed.
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        libpq5 \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini .
COPY alembic ./alembic
COPY app ./app
COPY scripts ./scripts

RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin appuser \
    && mkdir -p /data/media /data/backups \
    && chown -R appuser:appuser /app /data

USER appuser

EXPOSE 8000

# Shallow liveness — deep readiness is /api/v1/health/ready
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8000/api/v1/health || exit 1

# Production default: multi-worker uvicorn (override UVICORN_WORKERS in compose/env)
ENV UVICORN_WORKERS=2
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers ${UVICORN_WORKERS:-2} --proxy-headers --forwarded-allow-ips='*' --log-level $(echo \"${LOG_LEVEL:-info}\" | tr '[:upper:]' '[:lower:]')"]
