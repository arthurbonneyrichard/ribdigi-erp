#!/usr/bin/env bash
# RIBDIGI BUSINESS ERP — Cloud Agent start (idempotent, runs on every boot).
# Brings up PostgreSQL + Redis, ensures the app role/database exist, and applies
# Alembic migrations. Long-running app processes run as terminals (see environment.json).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "==> [start] PostgreSQL"
if ! sudo -u postgres pg_isready -q 2>/dev/null; then
  # Clear a stale postmaster pid left over from a snapshot, then start the cluster.
  sudo rm -f /var/lib/postgresql/16/main/postmaster.pid 2>/dev/null || true
  sudo pg_ctlcluster 16 main start || sudo pg_ctlcluster --force 16 main start
fi
# Wait for readiness (up to ~30s).
for _ in $(seq 1 30); do
  sudo -u postgres pg_isready -q 2>/dev/null && break
  sleep 1
done
sudo -u postgres pg_isready

echo "==> [start] ensure role + database"
sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='ribdigi'" | grep -q 1 \
  || sudo -u postgres psql -c "CREATE ROLE ribdigi WITH LOGIN SUPERUSER PASSWORD 'ribdigi';"
sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='ribdigi_erp'" | grep -q 1 \
  || sudo -u postgres createdb -O ribdigi ribdigi_erp

echo "==> [start] Redis"
if ! redis-cli ping >/dev/null 2>&1; then
  sudo redis-server /etc/redis/redis.conf --daemonize yes
fi
for _ in $(seq 1 15); do
  redis-cli ping >/dev/null 2>&1 && break
  sleep 1
done
redis-cli ping

echo "==> [start] Alembic migrations"
cd "$REPO_ROOT/backend"
# shellcheck disable=SC1091
source .venv/bin/activate
export PYTHONPATH="$REPO_ROOT/backend"
python -m alembic upgrade head
deactivate

echo "==> [start] ready (Postgres + Redis up, schema migrated)"
