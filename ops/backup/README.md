# Logical backup offsite sync (Stage 26 W1)

Mirrors encrypted `.ribbak` archives (Stages 5/10/18/23) to S3-compatible storage alongside WAL segments.

| File | Role |
|------|------|
| `sync-ribbak-offsite.sh.example` | `aws s3 sync` of `BACKUP_DIR` → `s3://…/ribdigi/logical/ribbak/` |
| `docker-compose.wal-drill.example.yml` | Optional staging stack snippet (Postgres + MinIO) |

RIBDIGI `create_backup` still writes local `BACKUP_DIR` first. Stage 27 B1 adds opt-in in-app upload (`BACKUP_OFFSITE_UPLOAD_ENABLED`); this script remains the bulk/cron mirror complement.

See `docs/DR_WAL_PITR_RUNBOOK.md` and `docs/DR_LOGICAL_BACKUP_RUNBOOK.md`.
