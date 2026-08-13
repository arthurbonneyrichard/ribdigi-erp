# Stage 167 Plan — Offline Complete E2E Hardening Fidelity

**Status:** Closed — exit met (H167x); freeze ADR-341  
**Base:** Catalog TTL + conflict UX polish + Hold reserve expiry  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Open ADR:** [ADR-340](ADR_340_STAGE167_OPEN.md)  
**Exit:** [STAGE_167_EXIT_CRITERIA.md](STAGE_167_EXIT_CRITERIA.md) · freeze [ADR-341](ADR_341_STAGE167_FREEZE.md)  
**Fidelity:** [STAGE_167_FIDELITY.md](STAGE_167_FIDELITY.md)  
**Impact audit:** [CHANGE_IMPACT_MVP_UPDATE_2026-08-13.md](CHANGE_IMPACT_MVP_UPDATE_2026-08-13.md)  
**Prior freeze:** [ADR-339](ADR_339_STAGE166_FREEZE.md)

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **T1** | Offline catalog TTL / refresh policy | P0 | COMPLETE |
| **U1** | Conflict re-apply UX polish | P0 | COMPLETE |
| **E1** | Hold soft-reserve expiry / cleanup | P0 | COMPLETE |
| **D1** | Spec / readiness / launch / deploy / security fidelity sync | P1 | COMPLETE |
| **H167x** | Stage 167 exit criteria + freeze ADR | Exit | COMPLETE |

## Explicitly out of this pass

- Claiming Offline Complete
- Fabricated MRR; ADR-002/003/005 Completes
- Billers CRUD; main `ci.yml` deploy
- Reopen Stages 1–166 feature scopes
- Caching `/api/v1/*` or tokens in the service worker

## Acceptance

- [x] Catalog meta includes TTL/expires_at; POS shows TTL expired + refresh CTA.
- [x] Conflict list shows summary reason / client keys / accept_client policy.
- [x] Soft-reserved holds set `expires_at`; expire-stale releases `reserved_qty`.
- [x] Automated proof: `test_stage167_catalog_ttl_t1.py`, `test_stage167_conflict_ux_u1.py`, `test_stage167_hold_expiry_e1.py`.
