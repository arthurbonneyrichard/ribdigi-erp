# Disaster Recovery Runbook — WAL / PITR + S3 Offsite (Stage 26 W1)

**Scope:** Stage 26 W1 — PostgreSQL WAL archiving strategy, S3-compatible offsite packaging for WAL + encrypted `.ribbak`, operator PITR outline  
**Related logical DR:** [DR_LOGICAL_BACKUP_RUNBOOK.md](DR_LOGICAL_BACKUP_RUNBOOK.md) (Stages 5/10/18/23 — Complete)  
**Evidence:** `backend/tests/test_wal_pitr_w1.py` → `/opt/cursor/artifacts/dr/stage26_w1_wal_pitr_strategy.json`  
**Configs:** `ops/postgres/`, `ops/backup/`

This runbook documents the **MVP WAL/PITR strategy** and offsite fidelity. It does **not** claim that CI executes `pg_basebackup` / WAL replay or that a managed-cloud PITR product is wired. Stage 27 B1 adds opt-in `create_backup` → S3 upload (`BACKUP_OFFSITE_UPLOAD_ENABLED`).

## Relationship to logical `.ribbak` DR

| Layer | Role | Status |
|-------|------|--------|
| Logical `.ribbak` | Tenant-scoped encrypted business-data restore (API guarded) | Complete (Stages 5/10/18/23) |
| WAL + base backup | Infrastructure point-in-time recovery of the Postgres cluster | Strategy Complete (MVP) — Stage 26 W1 |
| `.ribbak` offsite sync | Mirror encrypted archives to S3-compatible store | Script Complete (MVP) — Stage 26 W1 |

Use logical restore for tenant data accidents. Use WAL/PITR for cluster-level corruption, disk loss, or infra RPO targets.

## RTO / RPO (infrastructure strategy)

| Metric | Target (strategy) | Notes |
|--------|-------------------|-------|
| RPO | ≤ 15 minutes (with `archive_timeout` + continuous archive) | Depends on operator archive health |
| RTO | ≤ 4 hours (operator staging drill) | Base restore + WAL replay; not CI-certified |

## S3-compatible layout

```
s3://<bucket>/ribdigi/postgres/base/     # pg_basebackup / snapshots
s3://<bucket>/ribdigi/postgres/wal/      # archived WAL segments
s3://<bucket>/ribdigi/logical/ribbak/    # mirrored .ribbak archives
```

Reuse existing MinIO / `S3_ENDPOINT` credentials patterns from media storage (`STORAGE_BACKEND=s3`). Prefer a dedicated backup bucket or prefix with least-privilege IAM.

## Enable WAL archiving (staging / production)

1. Install `ops/postgres/archive-wal-to-s3.sh.example` as `/usr/local/bin/archive-wal-to-s3.sh` (executable).
2. Set `WAL_S3_BUCKET`, optional `WAL_S3_PREFIX`, `S3_ENDPOINT`, and AWS-compatible credentials.
3. Apply settings from `ops/postgres/postgresql-wal-archive.conf.example` (`wal_level=replica`, `archive_mode=on`, `archive_command`, `archive_timeout`).
4. Reload/restart Postgres; confirm `archive_mode` is on (`SHOW archive_mode;`).
5. Take a base backup (`pg_basebackup` or managed snapshot) → upload under `ribdigi/postgres/base/`.
6. Generate traffic / wait `archive_timeout`; confirm objects appear under `ribdigi/postgres/wal/`.

Optional compose sketch: `ops/backup/docker-compose.wal-drill.example.yml`.

## Offsite logical archives

1. Ensure scheduled / manual `.ribbak` jobs write to `BACKUP_DIR` (existing API).
2. Run `ops/backup/sync-ribbak-offsite.sh.example` on a cron (e.g. hourly) with `BACKUP_OFFSITE_S3_BUCKET` / `BACKUP_OFFSITE_S3_PREFIX`.
3. Verify object listing matches local `.ribbak` filenames + checksums when sampled.

Stage **27** **B1**: opt-in automatic in-app upload from `create_backup` when `BACKUP_OFFSITE_UPLOAD_ENABLED=true` (bucket `BACKUP_OFFSITE_S3_BUCKET`, prefix `BACKUP_OFFSITE_S3_PREFIX`, credentials via `S3_ACCESS_KEY` / `S3_SECRET_KEY` / `S3_ENDPOINT`). Upload failure marks the job failed and notifies admins (`Backup failed`) — local `.ribbak` is retained. Evidence: `test_backup_offsite_b1.py`. Operator `aws s3 sync` script remains for bulk/cron mirror.

## Operator PITR drill (staging — not CI)

1. Provision an empty Postgres data directory.
2. Restore the latest base backup.
3. Configure `restore_command` to fetch from `s3://…/ribdigi/postgres/wal/%f` (aws/mc helper).
4. Set recovery target time (or promote immediately after catch-up).
5. Start Postgres; verify `pg_is_in_recovery()` then promote.
6. Smoke: `GET /api/v1/health/ready`, login, spot-check a tenant.
7. Record outcomes in the ops change log. CI writes strategy evidence only (`stage26_w1_wal_pitr_strategy.json` with `operator_pitr_drill_required=true`).

## Failure / escalation

| Symptom | Action |
|---------|--------|
| `archive_command` failures | Check credentials/endpoint; inspect Postgres log; pause write-heavy jobs if WAL fills |
| Missing WAL gap | Stop; take a new base backup; do not claim continuous PITR until gap closed |
| Offsite sync failure | Keep local `BACKUP_DIR`; fix IAM/network; re-run sync; alert onboarding |

## Explicitly deferred

- CI-executed `pg_basebackup` / WAL replay certificate
- Managed RDS/Aurora continuous PITR product wiring
- Hosted managed-cloud PITR product automation (operator)
- Schema-per-tenant restore (ADR-001); restore-to-new-tenant
- Cross-region replication automation

## Sign-off

Stage 26 W1 strategy is met when versioned configs + this runbook exist, the guard test passes, and PRODUCTION_READINESS WAL gate is Complete (MVP) with Remaining limited to operator staging PITR drill execution and managed-cloud automation.
