# Stage 125 Plan — Tenant MVP Inactive Liquid Accounts, Recurring Expenses & Liquid/Recurring CSV Export Fidelity

**Status:** Closed — exit met (H125x); freeze ADR-257  
**Base:** Inactive Liquid Accounts Honesty + Paused Recurring Expenses Honesty + Liquid & Recurring CSV Export → Tenant MVP Inactive Liquid Accounts, Recurring Expenses & Liquid/Recurring CSV Export Fidelity  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Open ADR:** [ADR-256](ADR_256_STAGE125_OPEN.md)  
**Exit:** [STAGE_125_EXIT_CRITERIA.md](STAGE_125_EXIT_CRITERIA.md) · freeze [ADR-257](ADR_257_STAGE125_FREEZE.md)  
**Fidelity:** [STAGE_125_FIDELITY.md](STAGE_125_FIDELITY.md)  
**Prior freeze:** [ADR-255](ADR_255_STAGE124_FREEZE.md) · [STAGE_124_EXIT_CRITERIA.md](STAGE_124_EXIT_CRITERIA.md)

## Delivery packs (derived)

```
Inactive Liquid Accounts Honesty Pack
        +
Paused Recurring Expenses Honesty Pack
        +
Liquid & Recurring CSV Export Pack
        ↓
Tenant MVP Inactive Liquid Accounts, Recurring Expenses & Liquid/Recurring CSV Export Fidelity
```

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **L1** | Inactive liquid cash/bank accounts honesty + UI/Shell | P0 | COMPLETE |
| **R1** | Paused recurring expenses honesty + UI/Shell | P0 | COMPLETE |
| **X1** | Liquid & recurring CSV export (`GET /accounting/liquid-accounts/export`, `/expenses/recurring/export`) | P0 | COMPLETE |
| **D1** | Spec / readiness / launch / deploy / security fidelity sync | P1 | COMPLETE |
| **H125x** | Stage 125 exit criteria + freeze ADR | Exit | COMPLETE |

## Explicitly out of this pass

- Paid billing / fabricated MRR / checkout / `subscriptions_live_claimed` Complete (ADR-002)
- User↔Store membership Complete (ADR-005)
- Hard-delete archival Complete (ADR-003)
- Impersonation; POS Hold/Resume; full Billers CRUD; parallel Income; WYSIWYG designer Complete
- Bank-connection inactive+export; webhooks export; FX CSV; PO OCR; main `ci.yml` deploy jobs
- Reopening Stages 80–124 frozen feature scopes (esp. Stage 123 COA export)

## L1 acceptance criteria

- [x] `GET/PATCH /accounting/liquid-accounts?is_active=` (+ `active_only`); Cash & Bank filter; Shell Active/Inactive Liquid Accounts; Deactivate/Reactivate.
- [x] Automated proof: `backend/tests/test_stage125_inactive_liquid_accounts_l1.py`.

## R1 acceptance criteria

- [x] `GET /expenses/recurring?is_active=true|false` (+ `active_only`); Expenses Recurring filter; Shell Active/Paused Recurring; Pause/Resume.
- [x] Automated proof: `backend/tests/test_stage125_inactive_recurring_expenses_r1.py`.

## X1 acceptance criteria

- [x] `GET /accounting/liquid-accounts/export`, `/expenses/recurring/export`; Export buttons.
- [x] Automated proof: `backend/tests/test_stage125_liquid_recurring_export_x1.py`.

## D1 / H125x acceptance criteria

- [x] `docs/STAGE_125_FIDELITY.md` + exit/freeze ADR-257.
- [x] Automated proof: `test_stage125_fidelity_d1.py`, `test_stage125_exit_h125x.py`.
