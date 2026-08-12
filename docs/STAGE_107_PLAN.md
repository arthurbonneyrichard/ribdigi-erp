# Stage 107 Plan — Tenant MVP POS Sections, Commerce Filters & Ops Leaves Ops

**Status:** Closed — exit met (H107x); freeze ADR-221  
**Base:** POS Sections Honesty + Commerce Filters Honesty + Ops Leaves Discoverability → Tenant MVP POS Sections, Commerce Filters & Ops Leaves Ops  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Open ADR:** [ADR-220](ADR_220_STAGE107_OPEN.md)  
**Exit:** [STAGE_107_EXIT_CRITERIA.md](STAGE_107_EXIT_CRITERIA.md) · freeze [ADR-221](ADR_221_STAGE107_FREEZE.md)  
**Fidelity:** [STAGE_107_FIDELITY.md](STAGE_107_FIDELITY.md)  
**Prior freeze:** [ADR-219](ADR_219_STAGE106_FREEZE.md) · [STAGE_106_EXIT_CRITERIA.md](STAGE_106_EXIT_CRITERIA.md)

## Delivery packs (derived)

```
POS Sections Honesty Pack
        +
Commerce Filters Honesty Pack
        +
Ops Leaves Discoverability Pack
        ↓
Tenant MVP POS Sections, Commerce Filters & Ops Leaves Ops
```

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **P1** | POS sections honesty | P0 | COMPLETE |
| **S1** | Commerce filters honesty | P0 | COMPLETE |
| **O1** | Ops leaves discoverability | P0 | COMPLETE |
| **D1** | Spec / readiness / launch / deploy / security fidelity sync | P1 | COMPLETE |
| **H107x** | Stage 107 exit criteria + freeze ADR | Exit | COMPLETE |

## Explicitly out of this pass

- Paid billing / fabricated MRR / checkout / `subscriptions_live_claimed` Complete (ADR-002)
- User↔Store membership Complete (ADR-005)
- Hard-delete archival Complete (ADR-003)
- Impersonation; POS Hold/Resume; full Billers CRUD; parallel Income; WYSIWYG; fiscal-period close
- Reopening Stages 80–106 frozen feature scopes; main `ci.yml` deploy jobs

## P1 acceptance criteria

- [x] POS `#shift` / `#cart` / `#receipt` anchors + Shell leaves; hash scroll (extends Stage 101 `#sessions`).
- [x] Automated proof: `backend/tests/test_stage107_pos_sections_p1.py`.

## S1 acceptance criteria

- [x] Sales `active_only` URL sync for customers/groups; inventory product list shareable `q` / `category_id` / `brand_id` (client-side).
- [x] Automated proof: `backend/tests/test_stage107_commerce_filters_s1.py`.

## O1 acceptance criteria

- [x] PlatformShell At-risk / New Tenants leaves; Backup `#history` Shell + hash honor.
- [x] Automated proof: `backend/tests/test_stage107_ops_leaves_o1.py`.

## D1 / H107x acceptance criteria

- [x] `docs/STAGE_107_FIDELITY.md` + exit/freeze ADR-221.
- [x] Automated proof: `test_stage107_fidelity_d1.py`, `test_stage107_exit_h107x.py`.
