# Stage 101 Plan — Tenant MVP Inventory Ops & Shift History Ops

**Status:** Closed — exit met (H101x); freeze ADR-209  
**Base:** Opening Stock & Movements Shell Discoverability + Recurring Expenses Leaf & Notification Deep-Link Honesty + POS Session History Discoverability → Tenant MVP Inventory Ops & Shift History Ops  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Open ADR:** [ADR-208](ADR_208_STAGE101_OPEN.md)  
**Exit:** [STAGE_101_EXIT_CRITERIA.md](STAGE_101_EXIT_CRITERIA.md) · freeze [ADR-209](ADR_209_STAGE101_FREEZE.md)  
**Fidelity:** [STAGE_101_FIDELITY.md](STAGE_101_FIDELITY.md)  
**Prior freeze:** [ADR-207](ADR_207_STAGE100_FREEZE.md) · [STAGE_100_EXIT_CRITERIA.md](STAGE_100_EXIT_CRITERIA.md)

## Delivery packs (derived)

```
Opening Stock & Movements Shell Discoverability Pack
        +
Recurring Expenses Leaf & Notification Deep-Link Honesty Pack
        +
POS Session History Discoverability Pack
        ↓
Tenant MVP Inventory Ops & Shift History Ops
```

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **O1** | Opening Stock & Movements Shell discoverability | P0 | COMPLETE |
| **E1** | Recurring Expenses leaf & notification deep-link honesty | P0 | COMPLETE |
| **P1** | POS session history discoverability | P0 | COMPLETE |
| **D1** | Spec / readiness / launch / deploy / security fidelity sync | P1 | COMPLETE |
| **H101x** | Stage 101 exit criteria + freeze ADR | Exit | COMPLETE |

## Explicitly out of this pass

- Paid billing / fabricated MRR / checkout / `subscriptions_live_claimed` Complete (ADR-002)
- User↔Store membership Complete (ADR-005)
- Hard-delete archival Complete (ADR-003)
- Impersonation; **POS Hold/Resume**; full Billers CRUD; parallel Income module; WYSIWYG designer; fiscal-period close console
- Reopening Stages 80–100 frozen feature scopes; main `ci.yml` deploy jobs

## O1 acceptance criteria

- [x] Shell Opening Stock / Movements; Catalog Categories `#categories` anchor; optional Movements `movement_type` URL sync.
- [x] Automated proof: `backend/tests/test_stage101_opening_movements_o1.py`.

## E1 acceptance criteria

- [x] Shell Recurring Expenses (+ Categories & budgets); `#recurring` / `#budgets` anchors; notification deep-links for expense/recurring; Notifications `status`/`group` URL sync.
- [x] Automated proof: `backend/tests/test_stage101_recurring_notify_e1.py`.

## P1 acceptance criteria

- [x] POS session history from `GET /pos/sessions`; shift report via existing report API; Shell POS Sessions → `/pos#sessions`.
- [x] Automated proof: `backend/tests/test_stage101_pos_sessions_p1.py`.

## D1 / H101x acceptance criteria

- [x] `docs/STAGE_101_FIDELITY.md` + exit/freeze ADR-209.
- [x] Automated proof: `test_stage101_fidelity_d1.py`, `test_stage101_exit_h101x.py`.
