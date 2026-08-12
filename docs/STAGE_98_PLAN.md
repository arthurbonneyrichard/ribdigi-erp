# Stage 98 Plan — Tenant MVP Ops Queue & Returns Honesty Ops

**Status:** Closed — exit met (H98x); freeze ADR-203  
**Base:** Expense Approval Queue Honesty + Returns Pipeline Discoverability + Stock Ops & Bank Surface Discoverability → Tenant MVP Ops Queue & Returns Honesty Ops  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Open ADR:** [ADR-202](ADR_202_STAGE98_OPEN.md)  
**Exit:** [STAGE_98_EXIT_CRITERIA.md](STAGE_98_EXIT_CRITERIA.md) · freeze [ADR-203](ADR_203_STAGE98_FREEZE.md)  
**Fidelity:** [STAGE_98_FIDELITY.md](STAGE_98_FIDELITY.md)  
**Prior freeze:** [ADR-201](ADR_201_STAGE97_FREEZE.md) · [STAGE_97_EXIT_CRITERIA.md](STAGE_97_EXIT_CRITERIA.md)

## Delivery packs (derived)

```
Expense Approval Queue Honesty Pack
        +
Returns Pipeline Discoverability Pack
        +
Stock Ops & Bank Surface Discoverability Pack
        ↓
Tenant MVP Ops Queue & Returns Honesty Ops
```

## Delivery rules

1. One workstream at a time (full AC + automated tests before the next).
2. Prefer extending expenses, sales/purchase returns, inventory tabs, accounting reconcile/cheques, credit kind — do not invent parallel consoles.
3. No demo data / fake MRR. No fabricated queue counts. No impersonation.
4. After each feature: tests → commit → push → PR update.
5. Do not reopen Stage 1–97 feature scopes. Main `ci.yml` stays deploy-free (**Stage 18 C1**).
6. ADR-002 / ADR-005 remain deferred; ADR-003 stays soft-delete-only (`hard_delete_claimed: false`).

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **Q1** | Expense approval queue honesty | P0 | COMPLETE |
| **R1** | Returns pipeline discoverability | P0 | COMPLETE |
| **O1** | Stock ops & bank surface discoverability | P0 | COMPLETE |
| **D1** | Spec / readiness / launch / deploy / security fidelity sync | P1 | COMPLETE |
| **H98x** | Stage 98 exit criteria + freeze ADR | Exit | COMPLETE |

## Explicitly out of this pass

- Paid billing / fabricated MRR / checkout / `subscriptions_live_claimed` Complete (ADR-002)
- User↔Store membership Complete (ADR-005)
- Hard-delete archival Complete (ADR-003)
- Impersonation into customer ERP
- Full Billers CRUD / performance suite
- Parallel Income approval module mirroring Expenses
- WYSIWYG document designer Complete
- Fiscal-period close console Complete
- POS Hold/Resume (new engine → later stage)
- Reopening Stages 80–97 frozen feature scopes
- Main `ci.yml` deploy jobs

## Q1 acceptance criteria

- [x] Optional `status` on `GET /expenses` (`pending`/`approved`/`rejected`); UI filter + URL sync; Shell Pending Expenses; `#approval-matrix` anchor; dashboard `pending_expenses` kpi link.
- [x] Automated proof: `backend/tests/test_stage98_expense_queue_q1.py`.

## R1 acceptance criteria

- [x] Shell Sales Returns / Purchase Returns; optional `status` on sales/purchase returns APIs + UI/URL sync (`return_status`); draft→post honesty copy for credit/debit notes.
- [x] Automated proof: `backend/tests/test_stage98_returns_pipeline_r1.py`.

## O1 acceptance criteria

- [x] Shell Stock Counts / Warehouse Transfers / Bank Reconciliation / Cheques; Credit `?kind=` URL sync + Outstanding Receivables / Payables deep-links; dashboard credit kpi_links use kind.
- [x] Automated proof: `backend/tests/test_stage98_stock_bank_o1.py`.

## D1 acceptance criteria

- [x] `docs/STAGE_98_FIDELITY.md` maps Q1–O1 → readiness / launch / deploy / security.
- [x] Automated proof: `backend/tests/test_stage98_fidelity_d1.py`.

## H98x acceptance criteria

- [x] `docs/STAGE_98_EXIT_CRITERIA.md` + `docs/ADR_203_STAGE98_FREEZE.md`.
- [x] Automated proof: `backend/tests/test_stage98_exit_h98x.py`.
