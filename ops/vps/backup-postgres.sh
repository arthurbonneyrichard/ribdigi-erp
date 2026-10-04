#!/usr/bin/env bash
# Logical PostgreSQL dump for Ribdigi production Compose stack.
# Writes a gzipped SQL dump to ./backups/ on the host (create the dir first).
#
# Usage (from repo root on the VPS):
#   mkdir -p backups && chmod 700 backups
#   ./ops/vps/backup-postgres.sh
#
set -euo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
OUT_DIR="${OUT_DIR:-./backups}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT_FILE="${OUT_DIR}/ribdigi_erp_${STAMP}.sql.gz"

mkdir -p "${OUT_DIR}"
chmod 700 "${OUT_DIR}"

# shellcheck disable=SC1091
if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1090
  source .env
  set +a
fi

POSTGRES_USER="${POSTGRES_USER:-ribdigi}"
POSTGRES_DB="${POSTGRES_DB:-ribdigi_erp}"

echo "Dumping ${POSTGRES_DB} as ${POSTGRES_USER} → ${OUT_FILE}"
docker compose -f "${COMPOSE_FILE}" exec -T postgres \
  pg_dump -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" --format=plain --no-owner --no-acl \
  | gzip -c > "${OUT_FILE}"

chmod 600 "${OUT_FILE}"
echo "OK: ${OUT_FILE} ($(du -h "${OUT_FILE}" | awk '{print $1}'))"
echo "Copy off-box (example): scp ${OUT_FILE} secure-host:/path/ribdigi-backups/"
