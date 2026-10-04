#!/usr/bin/env bash
# Restore a gzipped pg_dump into the production Postgres volume.
# WARNING: overwrites the target database. Stop writers first.
#
# Usage:
#   ./ops/vps/restore-postgres.sh ./backups/ribdigi_erp_YYYYMMDDTHHMMSSZ.sql.gz
#
set -euo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
DUMP_FILE="${1:-}"

if [[ -z "${DUMP_FILE}" || ! -f "${DUMP_FILE}" ]]; then
  echo "Usage: $0 <path-to-dump.sql.gz>" >&2
  exit 1
fi

# shellcheck disable=SC1091
if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1090
  source .env
  set +a
fi

POSTGRES_USER="${POSTGRES_USER:-ribdigi}"
POSTGRES_DB="${POSTGRES_DB:-ribdigi_erp}"

echo "About to RESTORE ${DUMP_FILE} into database ${POSTGRES_DB}."
echo "Recommended: scale down backend/celery first:"
echo "  docker compose -f ${COMPOSE_FILE} stop backend celery_worker celery_beat frontend"
read -r -p "Type RESTORE to continue: " confirm
if [[ "${confirm}" != "RESTORE" ]]; then
  echo "Aborted."
  exit 1
fi

echo "Dropping and recreating database ${POSTGRES_DB}..."
docker compose -f "${COMPOSE_FILE}" exec -T postgres \
  psql -U "${POSTGRES_USER}" -d postgres -v ON_ERROR_STOP=1 <<SQL
SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '${POSTGRES_DB}' AND pid <> pg_backend_pid();
DROP DATABASE IF EXISTS ${POSTGRES_DB};
CREATE DATABASE ${POSTGRES_DB} OWNER ${POSTGRES_USER};
SQL

echo "Loading dump..."
gunzip -c "${DUMP_FILE}" | docker compose -f "${COMPOSE_FILE}" exec -T postgres \
  psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -v ON_ERROR_STOP=1

echo "Restore complete. Start services and re-run migrations if needed:"
echo "  docker compose -f ${COMPOSE_FILE} start backend celery_worker celery_beat frontend"
echo "  docker compose -f ${COMPOSE_FILE} run --rm migrate"
