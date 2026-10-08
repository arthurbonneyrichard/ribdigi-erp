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

# Build arg busts Dokploy/BuildKit cache for application layers after deps.
# Bump RIBDIGI_BUILD_ID in docker-compose.dokploy.yml when migrations must ship.
ARG RIBDIGI_BUILD_ID=unknown
LABEL org.ribdigi.build_id="${RIBDIGI_BUILD_ID}"
RUN printf '%s\n' "${RIBDIGI_BUILD_ID}" > /app/.build-id

COPY alembic.ini .
COPY alembic ./alembic
COPY app ./app
COPY scripts ./scripts
COPY guides ./guides
# Authoritative image id lives in the backend context. Compose build-args alone
# did not rebuild the Dokploy image that still reports 20261003-live-test-store-scope.
COPY ribdigi-build-id.txt /tmp/ribdigi-build-id.txt

# Fail the image build if the production-critical idempotent marker is missing
# in BOTH the alembic tree and the runtime overlay used by entrypoint.
RUN MIG=alembic/versions/20260917_0106_transaction_client_request_id.py \
    && OVL=scripts/migrations_overlay/20260917_0106_transaction_client_request_id.py \
    && test -f "$MIG" && test -f "$OVL" \
    && grep -q 'RIBDIGI_0106_IF_NOT_EXISTS_V3' "$MIG" \
    && grep -q 'ADD COLUMN IF NOT EXISTS client_request_id' "$MIG" \
    && ! grep -E 'op\.add_column\(|batch\.add_column\(' "$MIG" \
    && ! grep -F 'ADD COLUMN client_request_id' "$MIG" \
    && cmp -s "$MIG" "$OVL" \
    && chmod +x scripts/docker-entrypoint.sh

# Fail the image unless this context has exactly one Alembic head.
# Dummy URL is never contacted: `alembic heads` reads the script directory only.
RUN set -eu; \
    DATABASE_URL=postgresql+asyncpg://verify:verify@127.0.0.1:9/ribdigi_verify_build_graph \
    python -m alembic heads > /tmp/alembic-heads.txt; \
    printf '%s\n' '20261008_0136 (head)' > /tmp/alembic-heads.expected; \
    tr -d '\r' < /tmp/ribdigi-build-id.txt | awk 'NF { print; exit }' > /app/.build-id; \
    if ! cmp -s /tmp/alembic-heads.expected /tmp/alembic-heads.txt \
        || ! grep -qx '20261008-alembic-single-head-0136' /app/.build-id \
        || ! test -f alembic/versions/20261008_0136_merge_offline_and_restaurant_heads.py; then \
      echo 'alembic heads output:'; \
      cat -A /tmp/alembic-heads.txt; \
      echo 'build id file:'; \
      cat -A /app/.build-id; \
      exit 1; \
    fi; \
    rm -f /tmp/alembic-heads.txt /tmp/alembic-heads.expected

ENV RIBDIGI_BUILD_ID=20261008-alembic-single-head-0136

RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin appuser \
    && mkdir -p /data/media /data/backups \
    && chown -R appuser:appuser /app /data

USER appuser

EXPOSE 8000

# Always validate/install idempotent 0106 before any service command
# (survives Dokploy UI command overrides that skip compose `command:`).
ENTRYPOINT ["/app/scripts/docker-entrypoint.sh"]

# Shallow liveness — deep readiness is /api/v1/health/ready
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8000/api/v1/health || exit 1

# Production default: multi-worker uvicorn (override UVICORN_WORKERS in compose/env)
ENV UVICORN_WORKERS=2
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers ${UVICORN_WORKERS:-2} --proxy-headers --forwarded-allow-ips='*' --log-level $(echo \"${LOG_LEVEL:-info}\" | tr '[:upper:]' '[:lower:]')"]
