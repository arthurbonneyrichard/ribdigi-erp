# Stage 129 Plan — Tenant MVP Admin Session Inventory, Notifications CSV & Backup-Job History Export Fidelity

**Status:** Closed — exit met (H129x); freeze ADR-265  
**Base:** Admin Session Inventory + Notifications CSV + Backup Job History Filter & CSV → Tenant MVP Admin Session Inventory, Notifications CSV & Backup-Job History Export Fidelity  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Open ADR:** [ADR-264](ADR_264_STAGE129_OPEN.md)  
**Exit:** [STAGE_129_EXIT_CRITERIA.md](STAGE_129_EXIT_CRITERIA.md) · freeze [ADR-265](ADR_265_STAGE129_FREEZE.md)  
**Fidelity:** [STAGE_129_FIDELITY.md](STAGE_129_FIDELITY.md)  
**Prior freeze:** [ADR-263](ADR_263_STAGE128_FREEZE.md) · [STAGE_128_EXIT_CRITERIA.md](STAGE_128_EXIT_CRITERIA.md)

## Delivery packs (derived)

```
Admin Session Inventory + CSV Pack
        +
Notifications CSV Pack
        +
Backup Job Status Filter & CSV Pack
        ↓
Tenant MVP Admin Session Inventory, Notifications CSV & Backup-Job History Export Fidelity
```

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **A1** | Tenant-wide admin session inventory + secret-free CSV + UI/Shell | P0 | COMPLETE |
| **N1** | Notifications CSV + Notifications UI | P0 | COMPLETE |
| **B1** | Backup job status filter + metadata CSV + UI/Shell | P0 | COMPLETE |
| **D1** | Spec / readiness / launch / deploy / security fidelity sync | P1 | COMPLETE |
| **H129x** | Stage 129 exit criteria + freeze ADR | Exit | COMPLETE |

## Explicitly out of this pass

- Paid billing Complete (ADR-002); User↔Store membership (ADR-005); Hard-delete Complete (ADR-003)
- Impersonation; POS Hold/Resume; Billers CRUD; parallel Income; WYSIWYG Complete; PO OCR
- Admin remote-revoke of other users' sessions; API-key un-revoke; FX soft-`is_active`
- Main `ci.yml` deploy; reopen Stages 1–128

## A1 acceptance criteria

- [x] `GET /auth/tenant-sessions?status=active|revoked|all` (+ `active_only`); Security Tenant sessions; Shell Tenant Active/Revoked Sessions; `GET /auth/tenant-sessions/export` without refresh-token secrets.
- [x] Automated proof: `backend/tests/test_stage129_admin_sessions_a1.py`.

## N1 acceptance criteria

- [x] `GET /notifications/export` honoring status/group/category; Notifications Export button.
- [x] Automated proof: `backend/tests/test_stage129_notifications_export_n1.py`.

## B1 acceptance criteria

- [x] `GET /backup?status=` + `GET /backup/export` (metadata only); Backup filter + Export; Shell Completed/Failed Backups.
- [x] Automated proof: `backend/tests/test_stage129_backup_jobs_b1.py`.

## D1 / H129x acceptance criteria

- [x] `docs/STAGE_129_FIDELITY.md` + exit/freeze ADR-265.
- [x] Automated proof: `test_stage129_fidelity_d1.py`, `test_stage129_exit_h129x.py`.
