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

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Context is the repo root so this layer sees .git (Dokploy clone) and the
# stamp file. A Dockerfile-only edit is not enough when the Dockerfile is
# excluded from the context hash; the stamp file is in the context and changes
# when the source revision changes.
ARG RIBDIGI_SOURCE_REV=unknown
ENV RIBDIGI_SOURCE_REV=${RIBDIGI_SOURCE_REV}
COPY backend/ribdigi-build-id.txt /tmp/ribdigi-build-id.txt
COPY backend/scripts/resolve_source_revision.py /tmp/resolve_source_revision.py
COPY .git /tmp/dotgit
RUN python /tmp/resolve_source_revision.py \
    && grep -Eq '^[0-9a-f]{12}$' /app/.build-id \
    && ! grep -Fxq '20261003-live-test-store-scope' /app/.build-id \
    && ! grep -Fxq '20261008-alembic-single-head-0136' /app/.build-id
LABEL org.ribdigi.build_id="${RIBDIGI_SOURCE_REV}"

COPY backend/alembic.ini ./alembic.ini
COPY backend/alembic ./alembic
COPY backend/app ./app
COPY backend/scripts ./scripts
COPY backend/guides ./guides

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
    tr -d '\r\n' < /app/.build-id > /tmp/build-id-one-line; \
    if ! test "$(wc -l < /tmp/alembic-heads.txt)" -eq 1 \
        || ! grep -Eqx '[0-9]{8}_[0-9]{4} \(head\)' /tmp/alembic-heads.txt \
        || ! grep -Eq '^[0-9a-f]{12}$' /tmp/build-id-one-line \
        || grep -Fxq '20261003-live-test-store-scope' /tmp/build-id-one-line \
        || grep -Fxq '20261008-alembic-single-head-0136' /tmp/build-id-one-line \
        || ! test -f alembic/versions/20261008_0136_merge_offline_and_restaurant_heads.py; then \
      echo 'alembic heads output:'; \
      cat -A /tmp/alembic-heads.txt; \
      echo 'build id file:'; \
      cat -A /app/.build-id; \
      exit 1; \
    fi; \
    rm -f /tmp/alembic-heads.txt /tmp/build-id-one-line

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
