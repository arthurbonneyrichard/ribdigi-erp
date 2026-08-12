# Stage 104 Plan — Tenant MVP Ledger Filters, Commerce Leaves & Admin Ops

**Status:** Closed — exit met (H104x); freeze ADR-215  
**Base:** Ledger Journal & Cheque Filter Honesty + Commerce Products / Purchase Invoices / Sales Status Leaves + Credit Section & Admin Roles Discoverability → Tenant MVP Ledger Filters, Commerce Leaves & Admin Ops  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Open ADR:** [ADR-214](ADR_214_STAGE104_OPEN.md)  
**Exit:** [STAGE_104_EXIT_CRITERIA.md](STAGE_104_EXIT_CRITERIA.md) · freeze [ADR-215](ADR_215_STAGE104_FREEZE.md)  
**Fidelity:** [STAGE_104_FIDELITY.md](STAGE_104_FIDELITY.md)  
**Prior freeze:** [ADR-213](ADR_213_STAGE103_FREEZE.md) · [STAGE_103_EXIT_CRITERIA.md](STAGE_103_EXIT_CRITERIA.md)

## Delivery packs (derived)

```
Ledger Journal & Cheque Filter Honesty Pack
        +
Commerce Products / Purchase Invoices / Sales Status Leaves Pack
        +
Credit Section & Admin Roles Discoverability Pack
        ↓
Tenant MVP Ledger Filters, Commerce Leaves & Admin Ops
```

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **A1** | Ledger journal & cheque filter honesty | P0 | COMPLETE |
| **I1** | Commerce products / purchase invoices / sales status leaves | P0 | COMPLETE |
| **R1** | Credit section & admin roles discoverability | P0 | COMPLETE |
| **D1** | Spec / readiness / launch / deploy / security fidelity sync | P1 | COMPLETE |
| **H104x** | Stage 104 exit criteria + freeze ADR | Exit | COMPLETE |

## Explicitly out of this pass

- Paid billing / fabricated MRR / checkout / `subscriptions_live_claimed` Complete (ADR-002)
- User↔Store membership Complete (ADR-005)
- Hard-delete archival Complete (ADR-003)
- Impersonation; POS Hold/Resume; full Billers CRUD; parallel Income; WYSIWYG; fiscal-period close
- Reopening Stages 80–103 frozen feature scopes; main `ci.yml` deploy jobs

## A1 acceptance criteria

- [x] Journal `status` / `store_id` URL sync; Cheques UI `direction`/`status` filters + URL; Shell unposted/posted journals and pending/received/issued cheques leaves.
- [x] Automated proof: `backend/tests/test_stage104_ledger_filters_a1.py`.

## I1 acceptance criteria

- [x] Shell Products, Purchase Invoices, Draft Invoices, Overdue Invoices leaves.
- [x] Automated proof: `backend/tests/test_stage104_commerce_leaves_i1.py`.

## R1 acceptance criteria

- [x] Credit `#aging` / `#early-pay` / `#exchange-rates` / `#payment-schedule` (+ related) Shell leaves; Roles `#custom` / `#system`; dashboard Custom Roles → `/admin/roles#custom`.
- [x] Automated proof: `backend/tests/test_stage104_credit_roles_r1.py`.

## D1 / H104x acceptance criteria

- [x] `docs/STAGE_104_FIDELITY.md` + exit/freeze ADR-215.
- [x] Automated proof: `test_stage104_fidelity_d1.py`, `test_stage104_exit_h104x.py`.
