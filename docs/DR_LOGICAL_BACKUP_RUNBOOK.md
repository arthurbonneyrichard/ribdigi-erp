# Disaster Recovery Runbook — Logical Tenant Backup (`.ribbak`)

**Scope:** Stage 5 B1 + Stage 10 B1 (media) + Stage 18 B1 (schedule / retention / failure notify) + Stage 19 R1 (LAUNCH §5 packaging evidence) + Stage 23 B1 (commercial MVP DR drill gate evidence) — encrypted logical tenant backup / guarded restore  
**Infrastructure WAL / PITR / S3 offsite:** Stage 26 W1 strategy — see [DR_WAL_PITR_RUNBOOK.md](DR_WAL_PITR_RUNBOOK.md) (`ops/postgres/`, `ops/backup/`, `test_wal_pitr_w1.py`). Stage 27 B1 opt-in automatic `.ribbak` upload from `create_backup` (`BACKUP_OFFSITE_UPLOAD_ENABLED`; `test_backup_offsite_b1.py`). Stage 28 R1 operator drill pack — [PITR_DRILL_PACK_MVP.md](PITR_DRILL_PACK_MVP.md) (`test_pitr_drill_pack_r1.py`); live staging PITR drill **execution** remains Remaining.  
**Out of scope (post-MVP for this logical runbook):** schema-per-tenant isolation (ADR-001); restore-to-new-tenant. Infrastructure WAL/PITR operator staging drill remains Remaining under Stage 26 W1.

Stage 19 R1 automated packaging check: `backend/tests/test_reliability_cache_r1.py` (asserts this runbook + dry-run / `confirm_text=RESTORE` / WAL-PITR deferral).  
Stage 23 B1 commercial MVP gate proof: `backend/tests/test_logical_dr_drill_b1.py` → evidence artifact `/opt/ribdigi/artifacts/dr/stage23_b1_logical_drill.json` (create → dry-run → apply → verify + foreign-tenant 404).

## Purpose

Prove that a tenant can recover business data from an encrypted logical backup after accidental deletion or corruption, with checksum verification and a post-restore integrity proof.

## RTO / RPO (logical MVP)

| Metric | Target (logical restore) | Notes |
|--------|--------------------------|-------|
| RPO | Last successful `.ribbak` | Schedule via backup settings + Celery due runner |
| RTO | Operator-driven (maintenance window) | Dry-run → confirm `RESTORE` → verify |

Infrastructure PITR targets are documented under Stage 26 W1 (`docs/DR_WAL_PITR_RUNBOOK.md`); Stage 28 R1 packages the operator drill checklist (`docs/PITR_DRILL_PACK_MVP.md`); operator staging PITR drill **execution** remains Remaining.

## Preconditions

1. Operator has `company_admin` or `super_admin`.
2. `BACKUP_DIR` is writable; `BACKUP_ENCRYPTION_KEY` (or JWT-derived key) matches the key used to create the archive.
3. Maintenance window: notify users, close POS sessions, pause scheduled jobs when possible.
4. Prefer creating a **fresh safety backup** of the current (broken) state before applying restore.

## Drill procedure (quarterly)

1. **Create backup** — `POST /api/v1/backup` typed body `BackupCreateBody` `{ "notes"? }` (`extra=forbid`; unknown keys → **422**). Optional `notes` ∈ `BackupNotesValue` (strip; 1–500; ≥1 letter/digit; no `://`/`@`; omit/`null` → no notes; blank/`!!!`/`http://…` → **422** — was free `str` max_length=500). Backup UI **Backup notes** input (`aria-label`; blank omitted as `null`). Or rely on schedule. Record `backup_id`, filename, and `checksum_sha256`.
1b. **List backups** — `GET /api/v1/backup` optional Query `status` ∈ `pending`|`completed`|`failed`|`restoring` (schema Query `Literal` + strip/lower; omit → all; blank/invalid → **422**). Backup UI **Backup job status filter** (`backupManageFilter`).
2. **Download** (optional) — `GET /api/v1/backup/{id}/download`; confirm `X-Checksum-SHA256`.
3. **Simulate loss** (staging only) — mutate or delete a known product/party field that exists in the backup.
4. **Dry-run** — `POST /api/v1/backup/{id}/restore` with typed `BackupRestoreBody` `{"dry_run": true}` (`extra=forbid`). Confirm `valid`, `record_counts`, tenant match.
5. **Apply restore** — `POST /api/v1/backup/{id}/restore` with:
   ```json
   {"dry_run": false, "confirm": true, "confirm_text": "RESTORE"}
   ```
   Omit/wrong `confirm_text` / unknown keys → **422** (was late **400** via free `dict`).
6. **Integrity proof** — response includes `proof.ok`, `proof.checked`, `proof.mismatches`. Also run typed `BackupVerifyBody` `{ "sample_limit"? }` (1–500; omit → 100; out of range / unknown keys → **422** — was silent clamp):
   `POST /api/v1/backup/{id}/verify`
7. **Audit** — confirm `restore_dry_run` / `restore_apply` / `restore_verify` events under `module=backup`.
8. **Pass criteria** — `proof.ok == true`, spot-check UI (catalog / customer), no cross-tenant leakage.

Automated coverage: `backend/tests/test_backup_restore_proof_b1.py`, `backend/tests/test_backup_media_b1.py` (Stage 10 B1 media), `backend/tests/test_backup_schedule_b1.py` (Stage 18 B1 schedule / retention / failure notify), `backend/tests/test_logical_dr_drill_b1.py` (Stage 23 B1 commercial MVP drill gate + evidence artifact), `backend/tests/test_backup_restore_isolation_r1.py` (2026-10-04 isolated sqlite drill).

## Isolated sqlite drill (2026-10-04)

This drill does not restore production. It uses the pytest in-memory sqlite engine and a temp `BACKUP_DIR`.

From `backend` on system Python 3.12:

```
python -m pytest tests/test_backup_restore_isolation_r1.py -q --tb=short
```

Result on 2026-10-04: **2 passed** in 5.44s (exit 0). An earlier run, before the store and failed-store assertions, was 2 passed in 8.25s.

The tests create a store, a warehouse linked to that store, a POS sale, a recorded `mobile_money` tender, a stock movement, and an audit row on one tenant, plus a queued offline conflict, then `POST /api/v1/backup`. Dry-run restore returns `valid` true and `applied` false, with the source company name and store/transaction counts. After corrupting those rows, clearing the warehouse `store_id`, and adding a second queued event, `POST /api/v1/backup/{id}/restore` with `confirm_text` `RESTORE` restores the first tenant's product, stock, sale, payment, movement, store, and warehouse link and keeps `tenant_id`. `POST /backup/{id}/verify` with `sample_limit` 100 returns `proof.ok`. The other tenant's product, invoice, store, company name, and company id stay unchanged. The tenant row itself is not rewritten. The pre-backup audit row remains. Both queued events remain because offline sync events are not in `DATASET_SPECS`; dismissing the first conflict still returns 200. A forced integrity failure returns **409** and does not leave the sentinel product name or sentinel store name committed.

Offline POS stays the only offline surface. This drill does not make the rest of the ERP available offline.


## Isolated Postgres restore (2026-10-05) — blocked

Checked 2026-10-05. Postgres is listening on 127.0.0.1:5432. That listener is Docker container `ribdigi-erp-postgres-1`. The only application database is `ribdigi_erp` (plus `postgres`, `template0`, and `template1`). There is no disposable database. `/data/backups` inside `ribdigi-erp-backend-1` is empty. No `.ribbak` archive was found in the production tree. This session did not create a backup, did not restore, and did not read or change rows in `ribdigi_erp`.

The 2026-10-04 sqlite result (2 passed, 5.44s) is not an operator Postgres restore. The green 2026-10-05 full pytest (2855 passed, 1 skipped, ended 2026-10-05T10:09:14Z) does not close this gate. No disposable database was created on `ribdigi-erp-postgres-1`, because that server holds the live local `ribdigi_erp` database.

Prerequisites, all required before a rehearsal starts:

- A Postgres instance that is not `ribdigi-erp-postgres-1` and not a production or staging server.
- A new empty database on that instance. Do not copy `ribdigi_erp`.
- A throwaway API process whose `DATABASE_URL` and `BACKUP_DIR` point only at that database and a private backup directory.
- One `.ribbak` created by that API from tenant data it just wrote. An empty database with no backup is not a restore.

Operator steps:

1. Start the throwaway API against the disposable database only.
2. Create a tenant, a store, and one queued offline sale on that API.
3. `POST /api/v1/backup`. Record backup id and checksum.
4. Corrupt one disposable row.
5. Dry-run `POST /api/v1/backup/{id}/restore` and confirm `applied` is false.
6. Apply with `confirm_text` `RESTORE`.
7. `POST /api/v1/backup/{id}/verify` and confirm the other tenant, if any, is unchanged.
8. Write backup id, checksum, dry-run, apply, and verify into this runbook. Label the result as a disposable rehearsal, not a production restore.

Do not restore into `ribdigi_erp` or any production or staging data.


## Schedule, retention, and failure alerts (Stage 18 B1)

1. **Configure** — `PATCH /api/v1/backup/settings` with `enabled`, `frequency` schema `Literal["daily","weekly"]` (omit = no change; blank/invalid → **422**), `retention_count` (1–365), `hour_utc` (0–23). Backup UI **Backup frequency** select (`aria-label`).
2. **Due runner** — `POST /api/v1/backup/run-due` (admin) or Celery beat `run-due-backups`. Returns `ran`/`reason` (`schedule_disabled` | `already_ran` | `before_hour` | `created` | `failed` | `dir_not_writable`). A failed schedule run returns `ran=false` — never a fake success.
3. **Retention** — after each successful backup, older completed jobs beyond `retention_count` are deleted (files + rows).
4. **Failure notify** — failed create persists `BackupJob.status=failed` and creates a tenant `system` notification titled **Backup failed** (visible to admins). Disk-not-writable on schedule also notifies.
5. **Storage** — MVP archives land under local `BACKUP_DIR` (encrypted `.ribbak`). Stage 26 W1 offsite mirror: `ops/backup/sync-ribbak-offsite.sh.example` → S3-compatible prefix. Stage 27 B1 opt-in in-app upload: `BACKUP_OFFSITE_UPLOAD_ENABLED` (`test_backup_offsite_b1.py`).

## Important restore semantics

- Restore is **upsert by primary key** for datasets in `DATASET_SPECS`. It does **not** wipe rows created after the backup timestamp.
- Cross-tenant restore is blocked (`tenant_id` must match).
- Users / sessions / RBAC roles are **not** fully covered by logical datasets; treat identity recovery separately if needed.
- Wrong encryption key → decrypt failure (400); tampered archive → checksum failure (400).
- **Media (Stage 10 B1):** `.ribbak` inner payload includes optional `media` map keyed by storage key (`content_type`, `size`, `sha256`, `data_b64`) for tenant-scoped uploads referenced by company/brand logos, product images, expense receipts, purchase-invoice attachments, and journal supporting documents. Apply restore writes those bytes back to `STORAGE_BACKEND` after row upsert. External `http(s)://` URLs are not archived. Missing files at backup time are counted as `media_missing` and omitted (backup still succeeds). Older archives without `media` remain restorable (DB-only).

## Failure / escalation

| Symptom | Action |
|---------|--------|
| Checksum / decrypt error | Stop; do not force-apply. Restore encryption key from secrets store; re-download archive. |
| `proof.ok` false after apply | Capture `mismatches`; restore from earlier backup or safety backup; open incident. |
| Disk / `BACKUP_DIR` not writable | Fix volume permissions; `ensure_backup_dir_writable` returns 503. |

## Sign-off

Record date, operator, `backup_id`, checksum, dry-run/apply/verify outcomes, and any mismatches in the ops incident or change log after each quarterly drill.

Stage 23 B1 CI/harness evidence: when `test_logical_dr_drill_b1.py` passes, it writes `/opt/ribdigi/artifacts/dr/stage23_b1_logical_drill.json` with `passed`, `backup_id`, checksum, proof flags, and `wal_pitr_deferred=true`.
