# Disaster Recovery Runbook — Logical Tenant Backup (`.ribbak`)

**Scope:** Stage 5 B1 + Stage 10 B1 (media) + Stage 18 B1 (schedule / retention / failure notify) + Stage 19 R1 (LAUNCH §5 packaging evidence) + Stage 23 B1 (commercial MVP DR drill gate evidence) — encrypted logical tenant backup / guarded restore  
**Infrastructure WAL / PITR / S3 offsite:** Stage 26 W1 strategy — see [DR_WAL_PITR_RUNBOOK.md](DR_WAL_PITR_RUNBOOK.md) (`ops/postgres/`, `ops/backup/`, `test_wal_pitr_w1.py`). Operator staging PITR drill execution and automatic `.ribbak` upload from `create_backup` remain Remaining.  
**Out of scope (post-MVP for this logical runbook):** schema-per-tenant isolation (ADR-001); restore-to-new-tenant. Infrastructure WAL/PITR operator staging drill remains Remaining under Stage 26 W1.

Stage 19 R1 automated packaging check: `backend/tests/test_reliability_cache_r1.py` (asserts this runbook + dry-run / `confirm_text=RESTORE` / WAL-PITR deferral).  
Stage 23 B1 commercial MVP gate proof: `backend/tests/test_logical_dr_drill_b1.py` → evidence artifact `/opt/cursor/artifacts/dr/stage23_b1_logical_drill.json` (create → dry-run → apply → verify + foreign-tenant 404).

## Purpose

Prove that a tenant can recover business data from an encrypted logical backup after accidental deletion or corruption, with checksum verification and a post-restore integrity proof.

## RTO / RPO (logical MVP)

| Metric | Target (logical restore) | Notes |
|--------|--------------------------|-------|
| RPO | Last successful `.ribbak` | Schedule via backup settings + Celery due runner |
| RTO | Operator-driven (maintenance window) | Dry-run → confirm `RESTORE` → verify |

Infrastructure PITR targets are documented under Stage 26 W1 (`docs/DR_WAL_PITR_RUNBOOK.md`); operator staging PITR drill execution remains Remaining.

## Preconditions

1. Operator has `company_admin` or `super_admin`.
2. `BACKUP_DIR` is writable; `BACKUP_ENCRYPTION_KEY` (or JWT-derived key) matches the key used to create the archive.
3. Maintenance window: notify users, close POS sessions, pause scheduled jobs when possible.
4. Prefer creating a **fresh safety backup** of the current (broken) state before applying restore.

## Drill procedure (quarterly)

1. **Create backup** — `POST /api/v1/backup` (or rely on schedule). Record `backup_id`, filename, and `checksum_sha256`.
2. **Download** (optional) — `GET /api/v1/backup/{id}/download`; confirm `X-Checksum-SHA256`.
3. **Simulate loss** (staging only) — mutate or delete a known product/party field that exists in the backup.
4. **Dry-run** — `POST /api/v1/backup/{id}/restore` with `{"dry_run": true}`. Confirm `valid`, `record_counts`, tenant match.
5. **Apply restore** — `POST /api/v1/backup/{id}/restore` with:
   ```json
   {"dry_run": false, "confirm": true, "confirm_text": "RESTORE"}
   ```
6. **Integrity proof** — response includes `proof.ok`, `proof.checked`, `proof.mismatches`. Also run:
   `POST /api/v1/backup/{id}/verify`
7. **Audit** — confirm `restore_dry_run` / `restore_apply` / `restore_verify` events under `module=backup`.
8. **Pass criteria** — `proof.ok == true`, spot-check UI (catalog / customer), no cross-tenant leakage.

Automated coverage: `backend/tests/test_backup_restore_proof_b1.py`, `backend/tests/test_backup_media_b1.py` (Stage 10 B1 media), `backend/tests/test_backup_schedule_b1.py` (Stage 18 B1 schedule / retention / failure notify), `backend/tests/test_logical_dr_drill_b1.py` (Stage 23 B1 commercial MVP drill gate + evidence artifact).

## Schedule, retention, and failure alerts (Stage 18 B1)

1. **Configure** — `PATCH /api/v1/backup/settings` with `enabled`, `frequency` (`daily`|`weekly`), `retention_count` (1–365), `hour_utc` (0–23).
2. **Due runner** — `POST /api/v1/backup/run-due` (admin) or Celery beat `run-due-backups`. Returns `ran`/`reason` (`schedule_disabled` | `already_ran` | `before_hour` | `created` | `failed` | `dir_not_writable`). A failed schedule run returns `ran=false` — never a fake success.
3. **Retention** — after each successful backup, older completed jobs beyond `retention_count` are deleted (files + rows).
4. **Failure notify** — failed create persists `BackupJob.status=failed` and creates a tenant `system` notification titled **Backup failed** (visible to admins). Disk-not-writable on schedule also notifies.
5. **Storage** — MVP archives land under local `BACKUP_DIR` (encrypted `.ribbak`). Stage 26 W1 offsite mirror: `ops/backup/sync-ribbak-offsite.sh.example` → S3-compatible prefix (automatic in-app upload Remaining).

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

Stage 23 B1 CI/harness evidence: when `test_logical_dr_drill_b1.py` passes, it writes `/opt/cursor/artifacts/dr/stage23_b1_logical_drill.json` with `passed`, `backup_id`, checksum, proof flags, and `wal_pitr_deferred=true`.
