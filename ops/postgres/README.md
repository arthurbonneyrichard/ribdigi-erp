# PostgreSQL operator examples

## Stage 26 W1 — WAL archive

Versioned operator configs for continuous WAL archiving to S3-compatible storage. These files are **not** applied by default `docker-compose` or CI.

| File | Role |
|------|------|
| `postgresql-wal-archive.conf.example` | `wal_level=replica`, `archive_mode=on`, `archive_command` |
| `archive-wal-to-s3.sh.example` | `archive_command` helper → `s3://…/ribdigi/postgres/wal/` |

### Staging outline (WAL)

1. Provision an S3-compatible bucket (MinIO in compose, or AWS).
2. Install `archive-wal-to-s3.sh` on the Postgres host; set `WAL_S3_BUCKET` / `S3_ENDPOINT` / credentials.
3. Include `postgresql-wal-archive.conf.example` settings and reload Postgres.
4. Take a base backup: `pg_basebackup -D …` (or managed snapshot) → upload under `ribdigi/postgres/base/`.
5. Confirm new WAL files appear under `ribdigi/postgres/wal/` after `archive_timeout`.
6. PITR drill (operator staging only — not CI): restore base + `recovery.signal` / `restore_command` to a target timestamp.

Authoritative procedure: `docs/DR_WAL_PITR_RUNBOOK.md`. Logical tenant DR remains `.ribbak` (`docs/DR_LOGICAL_BACKUP_RUNBOOK.md`).

## Stage 28 R1 — Operator PITR drill pack

Versioned checklist packaging for staging drills. **Not** CI `pg_basebackup` / WAL replay success.

| File | Role |
|------|------|
| `pitr-drill-checklist.json` | Seven operator steps + pass criteria; `operator_pitr_drill_executed: false` |
| `docs/PITR_DRILL_PACK_MVP.md` | MVP pack doc + honesty rules |

Evidence: `test_pitr_drill_pack_r1.py` → `/opt/cursor/artifacts/dr/stage28_r1_pitr_drill_pack.json`.

## Stage 27 P1 — PgBouncer

Optional connection pooler packaging. **Not** default compose/CI; **not** an in-cluster Helm claim.

| File | Role |
|------|------|
| `pgbouncer.ini.example` | listen `6432`, `pool_mode=transaction`, DB `ribdigi_erp` |
| `userlist.txt.example` | auth_file placeholder for role `ribdigi` |
| `docker-compose.pgbouncer.example.yml` | optional overlay service |

Authoritative MVP doc: `docs/PGBOUNCER_MVP.md` (`test_pgbouncer_p1.py`). Point `DATABASE_URL` at `pgbouncer:6432`; keep Alembic on `postgres:5432` when preferred.

## Stage 29 B2 — PgBouncer soak / pooler pack

Versioned soak checklist + optional in-cluster snippet. **Not** live soak Complete; **not** default Helm data plane.

| File | Role |
|------|------|
| `pgbouncer-soak-checklist.json` | Operator soak steps; `live_soak_executed: false` |
| `soak-evidence.example.json` | Run schema (`passed: false` placeholder) |
| `pgbouncer-deployment.example.yaml` | Optional Deployment/Service snippet |

Authoritative pack: `docs/PGBOUNCER_SOAK_PACK_MVP.md` (`test_pgbouncer_soak_b2.py`).
