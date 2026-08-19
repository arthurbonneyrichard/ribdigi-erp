# Stage 166 Plan — Offline Complete Hardening Fidelity

**Status:** Closed — exit met (H166x); freeze ADR-339  
**Base:** Offline catalog cache + accept_client re-apply + Hold soft reserve  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Open ADR:** [ADR-338](ADR_338_STAGE166_OPEN.md)  
**Exit:** [STAGE_166_EXIT_CRITERIA.md](STAGE_166_EXIT_CRITERIA.md) · freeze [ADR-339](ADR_339_STAGE166_FREEZE.md)  
**Fidelity:** [STAGE_166_FIDELITY.md](STAGE_166_FIDELITY.md)  
**Impact audit:** [CHANGE_IMPACT_MVP_UPDATE_2026-08-13.md](CHANGE_IMPACT_MVP_UPDATE_2026-08-13.md)  
**Prior freeze:** [ADR-337](ADR_337_STAGE165_FREEZE.md)

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **C1** | Offline catalog IndexedDB cache + POS stale-stock search | P0 | COMPLETE |
| **A1** | Conflict accept_client safe re-apply policy | P0 | COMPLETE |
| **S1** | Hold soft stock reservation (`product.reserved_qty`) | P0 | COMPLETE |
| **D1** | Spec / readiness / launch / deploy / security fidelity sync | P1 | COMPLETE |
| **H166x** | Stage 166 exit criteria + freeze ADR | Exit | COMPLETE |

## Explicitly out of this pass

- Claiming Offline Complete
- Silent re-apply that double-posts already-applied POS sales
- SO-linked `StockReservation` rows for Hold
- Billers CRUD; parallel Income; WYSIWYG; ADR-002/003/005 Completes
- Main `ci.yml` deploy; reopen Stages 1–165 feature scopes (except A1 supersession of Stage 165 R1 accept_client honesty)
- Caching `/api/v1/*` or tokens in the service worker

## Acceptance

- [x] Catalog cache from `/sync/pull`; POS offline search labels stock non-authoritative.
- [x] `accept_client` re-applies only when original op was never applied; applied POS blocked.
- [x] Hold `reserve_stock=true` soft-reserves `product.reserved_qty`; default remains park-only.
- [x] Automated proof: `test_stage166_catalog_c1.py`, `test_stage166_accept_a1.py`, `test_stage166_hold_reserve_s1.py`.
