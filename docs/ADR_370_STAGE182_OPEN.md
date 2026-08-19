# ADR-370: Stage 182 Open — Tenant MVP User↔Store Membership Remaining-Gate Index Fidelity

**Status:** Accepted  
**Date:** 2026-08-13  
**Related:** [ADR-369](ADR_369_STAGE181_FREEZE.md), [CHANGE_IMPACT_MVP_UPDATE_2026-08-13.md](CHANGE_IMPACT_MVP_UPDATE_2026-08-13.md), [STAGE_182_PLAN.md](STAGE_182_PLAN.md)

## Context

Stage 181 froze Billing Remaining-Gate Index (ADR-369). The approved runner-up outline packages a Tenant MVP user↔store membership remaining-gate index: a single index of ADR-005 / membership blockers (`user_store_membership_claimed` false, store-scoped RBAC Completes non-claim) with explicit non-claim — without claiming membership Complete.

## Decision

Open **Stage 182 — Tenant MVP User↔Store Membership Remaining-Gate Index Fidelity** with packs:

| Pack | Scope |
|------|--------|
| **I1** | Membership remaining-gate index hub — single membership non-claim index |
| **B1** | Blocker matrix — ADR-005 deferred, no users.store_id API, store-scoped RBAC non-claim, multi-store membership Remaining |
| **P1** | Pack pointers — ADR-005, E2E users/RBAC, deferred ADR register, Stage 81 store_scope adjacency |
| **D1 / H182x** | Fidelity cite sync + Stage 182 exit; freeze as **ADR-371** |

## Consequences

- Does **not** claim user↔store membership Complete, `users.store_id` API Complete, or store-scoped RBAC Completes beyond existing `stores.manager_id` / branch-dept scopes.
- Distinct from Stage 35 U1 / Stage 81 S1 packaging — this stage indexes membership Remaining gates.
- Honesty flags stay false.
- Stages 1–181 feature scopes remain frozen.
