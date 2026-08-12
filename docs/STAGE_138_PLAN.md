# Stage 138 Plan — Tenant MVP Early-Pay Settings CSV, Expense Approval Settings CSV & Purchasing Approval Settings CSV Export Fidelity

**Status:** Closed — exit met (H138x); freeze ADR-283  
**Base:** Early-Pay Settings CSV + Expense Approval Settings CSV + Purchasing Approval Settings CSV → Tenant MVP Early-Pay Settings CSV, Expense Approval Settings CSV & Purchasing Approval Settings CSV Export Fidelity  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Open ADR:** [ADR-282](ADR_282_STAGE138_OPEN.md)  
**Exit:** [STAGE_138_EXIT_CRITERIA.md](STAGE_138_EXIT_CRITERIA.md) · freeze [ADR-283](ADR_283_STAGE138_FREEZE.md)  
**Fidelity:** [STAGE_138_FIDELITY.md](STAGE_138_FIDELITY.md)  
**Prior freeze:** [ADR-281](ADR_281_STAGE137_FREEZE.md) · [STAGE_137_EXIT_CRITERIA.md](STAGE_137_EXIT_CRITERIA.md)

## Delivery packs (derived)

```
Early-Pay Settings CSV Pack
        +
Expense Approval Settings CSV Pack
        +
Purchasing Approval Settings CSV Pack
        ↓
Tenant MVP Early-Pay Settings CSV, Expense Approval Settings CSV & Purchasing Approval Settings CSV Export Fidelity
```

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **C1** | Early-pay settings CSV + Credit UI | P0 | COMPLETE |
| **E1** | Expense approval settings CSV + Expenses UI | P0 | COMPLETE |
| **P1** | Purchasing approval settings CSV + Purchasing UI | P0 | COMPLETE |
| **D1** | Spec / readiness / launch / deploy / security fidelity sync | P1 | COMPLETE |
| **H138x** | Stage 138 exit criteria + freeze ADR | Exit | COMPLETE |

## Explicitly out of this pass

- Paid billing Complete (ADR-002); User↔Store membership (ADR-005); Hard-delete Complete (ADR-003)
- Impersonation; POS Hold/Resume; Billers CRUD; parallel Income; WYSIWYG Complete; PO OCR
- Admin remote-revoke-others; API-key un-revoke; FX soft-`is_active`
- Main `ci.yml` deploy; reopen Stages 1–137
- Expense budgets / fiscal-period / account-transactions CSV; payment allocation line dumps

## C1 acceptance criteria

- [x] `GET /credit/settings/export`; Credit Export early-pay settings CSV.
- [x] Automated proof: `backend/tests/test_stage138_early_pay_settings_c1.py`.

## E1 acceptance criteria

- [x] `GET /expenses/settings/export`; Expenses Export approval settings CSV.
- [x] Automated proof: `backend/tests/test_stage138_expense_settings_e1.py`.

## P1 acceptance criteria

- [x] `GET /purchasing/settings/export`; Purchasing Export approval settings CSV.
- [x] Automated proof: `backend/tests/test_stage138_purchasing_settings_p1.py`.

## D1 / H138x acceptance criteria

- [x] `docs/STAGE_138_FIDELITY.md` + exit/freeze ADR-283.
- [x] Automated proof: `test_stage138_fidelity_d1.py`, `test_stage138_exit_h138x.py`.
