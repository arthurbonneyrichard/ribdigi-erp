# Logical backup offsite sync (Stage 26 W1)

Mirrors encrypted `.ribbak` archives (Stages 5/10/18/23) to S3-compatible storage alongside WAL segments.

| File | Role |
|------|------|
| `sync-ribbak-offsite.sh.example` | `aws s3 sync` of `BACKUP_DIR` → `s3://…/ribdigi/logical/ribbak/` |
| `docker-compose.wal-drill.example.yml` | Optional staging stack snippet (Postgres + MinIO) |

RIBDIGI `create_backup` still writes local `BACKUP_DIR` first. Automatic in-app S3 upload remains Remaining; this script is the MVP offsite packaging fidelity.

See `docs/DR_WAL_PITR_RUNBOOK.md` and `docs/DR_LOGICAL_BACKUP_RUNBOOK.md`.
