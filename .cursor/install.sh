#!/usr/bin/env bash
# RIBDIGI BUSINESS ERP — Cloud Agent install (idempotent, runs after checkout).
# Prepares durable, source-derived state: system packages, Python venv, Node deps,
# a local dev .env, and writable data directories. Services are started in start.sh.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "==> [install] system packages"
export DEBIAN_FRONTEND=noninteractive
sudo apt-get update -qq
sudo apt-get install -y -qq \
  postgresql postgresql-contrib \
  redis-server \
  tesseract-ocr \
  libpq-dev \
  python3-venv \
  build-essential

echo "==> [install] local data directories"
mkdir -p "$REPO_ROOT/.localdata/media" "$REPO_ROOT/.localdata/backups"

echo "==> [install] dev .env (created only if missing)"
if [ ! -f "$REPO_ROOT/.env" ]; then
  cat > "$REPO_ROOT/.env" <<ENV
APP_ENV=development
DEBUG=true
DATABASE_URL=postgresql+asyncpg://ribdigi:ribdigi@127.0.0.1:5432/ribdigi_erp
JWT_SECRET_KEY=dev-only-local-secret-key-change-me-0123456789abcdef
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7
REDIS_URL=redis://127.0.0.1:6379/0
RABBITMQ_URL=amqp://ribdigi:ribdigi@127.0.0.1:5672/
CELERY_BROKER_URL=redis://127.0.0.1:6379/2
CELERY_ENABLED=true
CELERY_TASK_ALWAYS_EAGER=false
SMS_ENABLED=false
EMAIL_ENABLED=false
S3_ENDPOINT=http://127.0.0.1:9000
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin
S3_BUCKET=ribdigi-dev
S3_REGION=us-east-1
S3_FORCE_PATH_STYLE=true
STORAGE_BACKEND=local
BACKUP_DIR=$REPO_ROOT/.localdata/backups
MEDIA_DIR=$REPO_ROOT/.localdata/media
CORS_ORIGINS=http://localhost:3000
FRONTEND_URL=http://localhost:3000
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
RATE_LIMIT_ENABLED=true
RATE_LIMIT_BACKEND=auto
RATE_LIMIT_REQUIRE_REDIS=false
RATE_LIMIT_PER_MINUTE=120
RATE_LIMIT_AUTH_PER_MINUTE=20
METRICS_ENABLED=true
REQUEST_LOG_ENABLED=true
LOG_LEVEL=INFO
WEBAUTHN_RP_ID=localhost
WEBAUTHN_RP_NAME=RIBDIGI ERP
WEBAUTHN_ORIGIN=http://localhost:3000
POS_DRAWER_FALLBACK_MODE=mock
ALLOW_DEVELOPMENT_SEED=true
ENV
  echo "    wrote $REPO_ROOT/.env"
else
  echo "    .env already present — leaving untouched"
fi

echo "==> [install] backend Python venv + deps"
cd "$REPO_ROOT/backend"
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip -q
pip install -q -r requirements.txt
deactivate

echo "==> [install] frontend Node deps"
cd "$REPO_ROOT/frontend"
npm ci

echo "==> [install] done"
