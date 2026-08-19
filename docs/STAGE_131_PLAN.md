# Stage 131 Plan — Tenant MVP Journal Entry CSV, Bank Statement Status & Email-Settings Export Fidelity

**Status:** Closed — exit met (H131x); freeze ADR-269  
**Base:** Journal Entry CSV + Bank Statement Status & CSV + Email-Settings Export → Tenant MVP Journal Entry CSV, Bank Statement Status & Email-Settings Export Fidelity  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Open ADR:** [ADR-268](ADR_268_STAGE131_OPEN.md)  
**Exit:** [STAGE_131_EXIT_CRITERIA.md](STAGE_131_EXIT_CRITERIA.md) · freeze [ADR-269](ADR_269_STAGE131_FREEZE.md)  
**Fidelity:** [STAGE_131_FIDELITY.md](STAGE_131_FIDELITY.md)  
**Prior freeze:** [ADR-267](ADR_267_STAGE130_FREEZE.md) · [STAGE_130_EXIT_CRITERIA.md](STAGE_130_EXIT_CRITERIA.md)

## Delivery packs (derived)

```
Journal Entry Header CSV Pack
        +
Bank Statement Status & CSV Pack
        +
Email Settings Export Pack
        ↓
Tenant MVP Journal Entry CSV, Bank Statement Status & Email-Settings Export Fidelity
```

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **J1** | Journal entry header CSV honoring status/store_id + Accounting UI | P0 | COMPLETE |
| **B1** | Bank statement status honesty + CSV + UI/Shell | P0 | COMPLETE |
| **E1** | Email/SMTP settings CSV (secret-free) + Company UI | P0 | COMPLETE |
| **D1** | Spec / readiness / launch / deploy / security fidelity sync | P1 | COMPLETE |
| **H131x** | Stage 131 exit criteria + freeze ADR | Exit | COMPLETE |

## Explicitly out of this pass

- Paid billing Complete (ADR-002); User↔Store membership (ADR-005); Hard-delete Complete (ADR-003)
- Impersonation; POS Hold/Resume; Billers CRUD; parallel Income; WYSIWYG Complete; PO OCR
- Admin remote-revoke-others; API-key un-revoke; FX soft-`is_active`
- Main `ci.yml` deploy; reopen Stages 1–130
- Journal line dump in CSV; SMTP password in export

## J1 acceptance criteria

- [x] `GET /accounting/journal-entries/export` honoring status/store_id; Accounting Export journals CSV button.
- [x] Automated proof: `backend/tests/test_stage131_journals_export_j1.py`.

## B1 acceptance criteria

- [x] `GET /accounting/bank-statements?status=draft|in_progress|reconciled` + `GET /accounting/bank-statements/export`; filter; Shell Draft/In Progress/Reconciled Statements.
- [x] Automated proof: `backend/tests/test_stage131_bank_statements_b1.py`.

## E1 acceptance criteria

- [x] `GET /settings/email/export` secret-free (`has_password` only); Company Export email settings CSV button.
- [x] Automated proof: `backend/tests/test_stage131_email_settings_export_e1.py`.

## D1 / H131x acceptance criteria

- [x] `docs/STAGE_131_FIDELITY.md` + exit/freeze ADR-269.
- [x] Automated proof: `test_stage131_fidelity_d1.py`, `test_stage131_exit_h131x.py`.
