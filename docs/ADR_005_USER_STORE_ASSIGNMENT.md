# ADR-005: User Store Assignment

**Status:** Accepted — **Complete** (2026-09-15); flag default OFF (ops cutover)  
**Date:** 2026-08-09  
**Scaffold history:** [`ADR_005_MEMBERSHIP_SCAFFOLD.md`](ADR_005_MEMBERSHIP_SCAFFOLD.md)  
**Cutover design:** [`ADR_005_MEMBERSHIP_SCOPE_CUTOVER.md`](ADR_005_MEMBERSHIP_SCOPE_CUTOVER.md)  
**Ops checklist:** [`adr005_staging_soak_checklist.md`](adr005_staging_soak_checklist.md)

## Decision

1. **`user_store_memberships`** is the assignment model (assign/list/revoke + `/me/store-memberships` + `/stores#memberships`).
2. Default operational scope remains **`stores.manager_id`** while `STORE_MEMBERSHIP_SCOPE_ENABLED` is **false**.
3. When flag ON: store_manager = **`manager_id` ∪ memberships**; cashiers fail-closed via `store_visibility_ids`.
4. **ADR-005 Complete** = feature complete + automated flag-ON soak (SEC-M2 parallel). Complete ≠ production default ON.
5. **Store-scoped RBAC Complete** remains **MISSING** (separate continuum claim).
6. POS shift bind uses membership / Shell picker when scope is enabled (`posStoreBinding.ts`).

## Consequences

- BR-3.1 store assignment is Complete for membership + flag-gated scope wire.
- Flag OFF in prod examples is intentional ops cutover — not unfinished feature.
- Do not claim Offline Complete, 7-day VERIFIED, go-live, or paid billing Complete from this ADR.
