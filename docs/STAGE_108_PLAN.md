# Stage 108 Plan — Tenant MVP AI Analysis Leaves, Credit Statement & Users Directory Ops

**Status:** Closed — exit met (H108x); freeze ADR-223  
**Base:** AI Analysis Leaves Honesty + Credit Statement Surfaces Discoverability + Users Directory Leaves Discoverability → Tenant MVP AI Analysis Leaves, Credit Statement & Users Directory Ops  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Open ADR:** [ADR-222](ADR_222_STAGE108_OPEN.md)  
**Exit:** [STAGE_108_EXIT_CRITERIA.md](STAGE_108_EXIT_CRITERIA.md) · freeze [ADR-223](ADR_223_STAGE108_FREEZE.md)  
**Fidelity:** [STAGE_108_FIDELITY.md](STAGE_108_FIDELITY.md)  
**Prior freeze:** [ADR-221](ADR_221_STAGE107_FREEZE.md) · [STAGE_107_EXIT_CRITERIA.md](STAGE_107_EXIT_CRITERIA.md)

## Delivery packs (derived)

```
AI Analysis Leaves Honesty Pack
        +
Credit Statement Surfaces Discoverability Pack
        +
Users Directory Leaves Discoverability Pack
        ↓
Tenant MVP AI Analysis Leaves, Credit Statement & Users Directory Ops
```

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **A1** | AI analysis leaves honesty | P0 | COMPLETE |
| **C1** | Credit statement surfaces discoverability | P0 | COMPLETE |
| **U1** | Users directory leaves discoverability | P0 | COMPLETE |
| **D1** | Spec / readiness / launch / deploy / security fidelity sync | P1 | COMPLETE |
| **H108x** | Stage 108 exit criteria + freeze ADR | Exit | COMPLETE |

## Explicitly out of this pass

- Paid billing / fabricated MRR / checkout / `subscriptions_live_claimed` Complete (ADR-002)
- User↔Store membership Complete (ADR-005)
- Hard-delete archival Complete (ADR-003)
- Impersonation; POS Hold/Resume; full Billers CRUD; parallel Income; WYSIWYG; fiscal-period close
- Reopening Stages 80–107 frozen feature scopes; main `ci.yml` deploy jobs

## A1 acceptance criteria

- [x] Shell leaves for AI `#sales-analysis` / `#expense-analysis` / `#purchases-analysis` / `#cross-domain` / `#document` / `#customer` / `#report-generator` / `#low-stock` (anchors + scroll already exist).
- [x] Automated proof: `backend/tests/test_stage108_ai_analysis_a1.py`.

## C1 acceptance criteria

- [x] Shell leaves for Credit `#party-actions` / `#by-party` / `#statement` (extends Stage 104 aging/early-pay/FX/schedule).
- [x] Automated proof: `backend/tests/test_stage108_credit_statement_c1.py`.

## U1 acceptance criteria

- [x] Shell Active/Inactive Users leaves (`?is_active=true|false`); PlatformShell Active/Inactive staff leaves; pages keep URL sync.
- [x] Automated proof: `backend/tests/test_stage108_users_directory_u1.py`.

## D1 / H108x acceptance criteria

- [x] `docs/STAGE_108_FIDELITY.md` + exit/freeze ADR-223.
- [x] Automated proof: `test_stage108_fidelity_d1.py`, `test_stage108_exit_h108x.py`.
