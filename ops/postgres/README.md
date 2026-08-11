# PostgreSQL WAL archive examples (Stage 26 W1)

Versioned operator configs for continuous WAL archiving to S3-compatible storage. These files are **not** applied by default `docker-compose` or CI.

| File | Role |
|------|------|
| `postgresql-wal-archive.conf.example` | `wal_level=replica`, `archive_mode=on`, `archive_command` |
| `archive-wal-to-s3.sh.example` | `archive_command` helper → `s3://…/ribdigi/postgres/wal/` |

## Staging outline

1. Provision an S3-compatible bucket (MinIO in compose, or AWS).
2. Install `archive-wal-to-s3.sh` on the Postgres host; set `WAL_S3_BUCKET` / `S3_ENDPOINT` / credentials.
3. Include `postgresql-wal-archive.conf.example` settings and reload Postgres.
4. Take a base backup: `pg_basebackup -D …` (or managed snapshot) → upload under `ribdigi/postgres/base/`.
5. Confirm new WAL files appear under `ribdigi/postgres/wal/` after `archive_timeout`.
6. PITR drill (operator staging only — not CI): restore base + `recovery.signal` / `restore_command` to a target timestamp.

Authoritative procedure: `docs/DR_WAL_PITR_RUNBOOK.md`. Logical tenant DR remains `.ribbak` (`docs/DR_LOGICAL_BACKUP_RUNBOOK.md`).
