# Disaster Recovery Runbook — Logical Tenant Backup (`.ribbak`)

**Scope:** Stage 5 B1 — encrypted logical tenant backup / guarded restore  
**Out of scope (post-MVP):** PostgreSQL `pg_dump` / WAL archiving, S3 offsite PITR, schema-per-tenant isolation (ADR-001)

## Purpose

Prove that a tenant can recover business data from an encrypted logical backup after accidental deletion or corruption, with checksum verification and a post-restore integrity proof.

## RTO / RPO (logical MVP)

| Metric | Target (logical restore) | Notes |
|--------|--------------------------|-------|
| RPO | Last successful `.ribbak` | Schedule via backup settings + Celery due runner |
| RTO | Operator-driven (maintenance window) | Dry-run → confirm `RESTORE` → verify |

Infrastructure PITR targets in older docs remain **aspirational** until WAL/S3 work lands.

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

Automated coverage: `backend/tests/test_backup_restore_proof_b1.py`.

## Important restore semantics

- Restore is **upsert by primary key** for datasets in `DATASET_SPECS`. It does **not** wipe rows created after the backup timestamp.
- Cross-tenant restore is blocked (`tenant_id` must match).
- Users / sessions / RBAC roles are **not** fully covered by logical datasets; treat identity recovery separately if needed.
- Wrong encryption key → decrypt failure (400); tampered archive → checksum failure (400).

## Failure / escalation

| Symptom | Action |
|---------|--------|
| Checksum / decrypt error | Stop; do not force-apply. Restore encryption key from secrets store; re-download archive. |
| `proof.ok` false after apply | Capture `mismatches`; restore from earlier backup or safety backup; open incident. |
| Disk / `BACKUP_DIR` not writable | Fix volume permissions; `ensure_backup_dir_writable` returns 503. |

## Sign-off

Record date, operator, `backup_id`, checksum, dry-run/apply/verify outcomes, and any mismatches in the ops incident or change log after each quarterly drill.
