# Stage 182 Plan — Tenant MVP User↔Store Membership Remaining-Gate Index Fidelity

**Status:** Closed — exit met (H182x); freeze ADR-371  
**Base:** Membership remaining-gate hub + blocker matrix + ADR-005 / users-RBAC pointers  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Open ADR:** [ADR-370](ADR_370_STAGE182_OPEN.md)  
**Exit:** [STAGE_182_EXIT_CRITERIA.md](STAGE_182_EXIT_CRITERIA.md) · freeze [ADR-371](ADR_371_STAGE182_FREEZE.md)  
**Fidelity:** [STAGE_182_FIDELITY.md](STAGE_182_FIDELITY.md)  
**Impact audit:** [CHANGE_IMPACT_MVP_UPDATE_2026-08-13.md](CHANGE_IMPACT_MVP_UPDATE_2026-08-13.md)  
**Prior freeze:** [ADR-369](ADR_369_STAGE181_FREEZE.md)

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **I1** | Membership remaining-gate index hub | P0 | COMPLETE |
| **B1** | Membership blocker matrix | P0 | COMPLETE |
| **P1** | ADR-005 / E2E users-RBAC / deferred ADR pointers | P0 | COMPLETE |
| **D1** | Spec / readiness / launch / deploy / security fidelity sync | P1 | COMPLETE |
| **H182x** | Stage 182 exit criteria + freeze ADR | Exit | COMPLETE |

## Explicitly out of this pass

- Claiming user↔store membership Complete / `users.store_id` API
- Implementing multi-store membership tables
- Claiming billing / go-live / Offline Complete
- Main `ci.yml` deploy; reopen Stages 1–181 feature scopes

## Acceptance

- [x] Index hub keeps `user_store_membership_claimed` false.
- [x] Blocker matrix lists ADR-005, no store_id API, store-scoped RBAC non-claim honestly.
- [x] Pointers cite ADR-005 / E2E users-RBAC / deferred ADR register / Stage 81 adjacency.
- [x] Automated proof: `test_stage182_index_i1.py`, `test_stage182_blockers_b1.py`, `test_stage182_pointers_p1.py`.
