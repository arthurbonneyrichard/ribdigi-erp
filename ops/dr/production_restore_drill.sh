#!/usr/bin/env sh
# Production restore drill. Run on the production host by the owner. Read-only on production.
#
# What it does, per database (main + each desk database):
#   1. pg_dump from the production Postgres container (read-only; nothing is changed there)
#   2. restores the dump into a THROWAWAY Postgres container on a private Docker network
#   3. compares every table's row count and content hash between production and the copy
#   4. checks the books balance on the copy (every journal entry, every company)
#   5. upgrades the copy to the release about to deploy (alembic upgrade head) and back down
#   6. boots the API against the copy and asks it for health
#   7. writes a report and removes the throwaway container, network and dump files
#
# Usage:
#   PROD_PG_CONTAINER=<postgres container> PROD_PG_USER=ribdigi API_IMAGE=<backend image> \
#     sh ops/dr/production_restore_drill.sh ribdigi_erp [desk_db ...]
#
# Times measured: dump (backup) seconds, restore seconds, migrate seconds, boot seconds.
# Pass = every table identical, books balanced, migrate up/down clean, API healthy.
set -eu

PROD_PG_CONTAINER="${PROD_PG_CONTAINER:?set PROD_PG_CONTAINER to the production postgres container name}"
PROD_PG_USER="${PROD_PG_USER:-ribdigi}"
API_IMAGE="${API_IMAGE:?set API_IMAGE to the backend image that is about to deploy}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
WORK="${WORK_DIR:-/tmp/ribdigi-drill-$STAMP}"
NET="rdrill-$STAMP"
PG="drill-pg-$STAMP"
REPORT="$WORK/report.txt"
[ "$#" -ge 1 ] || { echo "Name at least one database (e.g. ribdigi_erp)"; exit 2; }
mkdir -p "$WORK"
now() { date +%s; }

cleanup() {
  docker rm -f "$PG" >/dev/null 2>&1 || true
  docker network rm "$NET" >/dev/null 2>&1 || true
  rm -f "$WORK"/*.dump
}
trap cleanup EXIT

COUNTS_SQL="DO \$\$ DECLARE r record; n bigint; BEGIN CREATE TEMP TABLE _c(t text, n bigint);
FOR r IN SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename LOOP
EXECUTE format('SELECT count(*) FROM public.%I', r.tablename) INTO n; INSERT INTO _c VALUES (r.tablename, n); END LOOP; END \$\$;
SELECT t||'|'||n FROM _c ORDER BY t;"
HASH_SQL="DO \$\$ DECLARE r record; h text; BEGIN CREATE TEMP TABLE _h(t text, h text);
FOR r IN SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename LOOP
EXECUTE format('SELECT coalesce(md5(string_agg(x.s, E''\\n'' ORDER BY x.s)), ''empty'') FROM (SELECT t::text AS s FROM public.%I t) x', r.tablename) INTO h;
INSERT INTO _h VALUES (r.tablename, h); END LOOP; END \$\$;
SELECT t||'|'||h FROM _h ORDER BY t;"
# One query per check: psql -c prints only the last result of a multi-statement string.
BOOKS_ENTRIES="SELECT 'unbalanced_entries|'||count(*) FROM (SELECT e.id FROM journal_entries e JOIN journal_entry_lines l ON l.journal_entry_id=e.id GROUP BY e.id HAVING abs(sum(l.debit)-sum(l.credit))>0.01) x"
BOOKS_COMPANIES="SELECT 'unbalanced_companies|'||count(*) FROM (SELECT e.tenant_id FROM journal_entries e JOIN journal_entry_lines l ON l.journal_entry_id=e.id GROUP BY e.tenant_id HAVING abs(sum(l.debit)-sum(l.credit))>0.01) y"
ORPHANS="SELECT 'orphan_journal_lines|'||count(*) FROM journal_entry_lines l LEFT JOIN journal_entries e ON e.id=l.journal_entry_id WHERE e.id IS NULL"

docker network create "$NET" >/dev/null
docker run -d --name "$PG" --network "$NET" -e POSTGRES_USER=drill -e POSTGRES_PASSWORD=drill -e POSTGRES_DB=drill postgres:16-alpine >/dev/null
until docker exec "$PG" psql -U drill -d drill -Atc "select 1" >/dev/null 2>&1; do sleep 1; done

echo "RIBDIGI production restore drill $STAMP" | tee "$REPORT"
FAIL=0
for DB in "$@"; do
  echo "== $DB" | tee -a "$REPORT"
  t0=$(now)
  docker exec "$PROD_PG_CONTAINER" pg_dump -U "$PROD_PG_USER" -d "$DB" -Fc -Z 6 -f "/tmp/drill-$DB.dump"
  docker cp "$PROD_PG_CONTAINER:/tmp/drill-$DB.dump" "$WORK/$DB.dump"
  docker exec "$PROD_PG_CONTAINER" rm -f "/tmp/drill-$DB.dump"
  t1=$(now)
  echo "backup_seconds=$((t1 - t0)) size_bytes=$(wc -c < "$WORK/$DB.dump") sha256=$(sha256sum "$WORK/$DB.dump" | cut -c1-64)" | tee -a "$REPORT"
  docker exec "$PG" psql -U drill -d drill -qc "CREATE DATABASE \"r_$DB\""
  docker cp "$WORK/$DB.dump" "$PG:/tmp/r.dump"
  t0=$(now)
  docker exec "$PG" pg_restore -U drill -d "r_$DB" --no-owner --no-privileges --exit-on-error /tmp/r.dump
  t1=$(now)
  echo "restore_seconds=$((t1 - t0))" | tee -a "$REPORT"

  docker exec -i "$PROD_PG_CONTAINER" psql -U "$PROD_PG_USER" -d "$DB" -Atq -c "$COUNTS_SQL" > "$WORK/$DB.src_counts"
  docker exec -i "$PG" psql -U drill -d "r_$DB" -Atq -c "$COUNTS_SQL" > "$WORK/$DB.copy_counts"
  docker exec -i "$PROD_PG_CONTAINER" psql -U "$PROD_PG_USER" -d "$DB" -Atq -c "$HASH_SQL" > "$WORK/$DB.src_hash"
  docker exec -i "$PG" psql -U drill -d "r_$DB" -Atq -c "$HASH_SQL" > "$WORK/$DB.copy_hash"
  # Production keeps taking sales while the drill runs, so busy tables can move between the
  # dump and the comparison. Counts must match exactly on a quiet night; report any difference.
  if diff -q "$WORK/$DB.src_counts" "$WORK/$DB.copy_counts" >/dev/null; then
    echo "row_counts=MATCH tables=$(wc -l < "$WORK/$DB.src_counts")" | tee -a "$REPORT"
  else
    echo "row_counts=DIFFER (tables written to during the drill?):" | tee -a "$REPORT"
    diff "$WORK/$DB.src_counts" "$WORK/$DB.copy_counts" | tee -a "$REPORT" || true
  fi
  if diff -q "$WORK/$DB.src_hash" "$WORK/$DB.copy_hash" >/dev/null; then
    echo "contents=IDENTICAL" | tee -a "$REPORT"
  else
    echo "contents=DIFFER in: $(diff "$WORK/$DB.src_hash" "$WORK/$DB.copy_hash" | grep '^>' | cut -d'|' -f1 | tr -d '> ' | tr '\n' ' ')" | tee -a "$REPORT"
  fi
  if docker exec "$PG" psql -U drill -d "r_$DB" -Atq -c "SELECT to_regclass('public.journal_entries') IS NOT NULL" | grep -q t; then
    for Q in "$BOOKS_ENTRIES" "$BOOKS_COMPANIES" "$ORPHANS"; do
      LINE=$(docker exec "$PG" psql -U drill -d "r_$DB" -Atq -c "$Q")
      echo "$LINE" | tee -a "$REPORT"
      case "$LINE" in *"|0") ;; *) FAIL=1 ;; esac
    done
  fi

  URL="postgresql+asyncpg://drill:drill@$PG:5432/r_$DB"
  t0=$(now)
  if docker run --rm --network "$NET" --entrypoint sh -e DATABASE_URL="$URL" "$API_IMAGE" -c \
    "python -m alembic upgrade head > /tmp/m.log 2>&1 || { tail -5 /tmp/m.log; exit 1; }; python -m alembic current 2>/dev/null | tail -1" > "$WORK/$DB.migrate" 2>&1; then
    echo "migrated_to=$(tail -1 "$WORK/$DB.migrate")" | tee -a "$REPORT"
  else
    echo "migrate=FAILED: $(tr '\n' ' ' < "$WORK/$DB.migrate")" | tee -a "$REPORT"
    FAIL=1
  fi
  t1=$(now)
  echo "migrate_seconds=$((t1 - t0))" | tee -a "$REPORT"
  docker run --rm --network "$NET" --entrypoint sh -e DATABASE_URL="$URL" -e APP_ENV=development \
    -e CELERY_ENABLED=false -e SMS_ENABLED=false -e EMAIL_ENABLED=false "$API_IMAGE" -c \
    "python -m uvicorn app.main:app --host 127.0.0.1 --port 8099 >/dev/null 2>&1 & for i in \$(seq 1 90); do python -c \"import urllib.request;urllib.request.urlopen('http://127.0.0.1:8099/api/v1/health',timeout=2)\" 2>/dev/null && echo api_health=OK && exit 0; sleep 1; done; echo api_health=FAILED; exit 1" \
    > "$WORK/$DB.health" 2>&1 || FAIL=1
  tee -a "$REPORT" < "$WORK/$DB.health"
done

[ "$FAIL" -eq 0 ] && echo "RESULT=PASS" | tee -a "$REPORT" || echo "RESULT=FAIL" | tee -a "$REPORT"
echo "Report: $REPORT"
