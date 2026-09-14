# ADR-005 Membership Scaffold (PARTIAL — not Complete)

**Status:** PARTIAL scaffold  
**Date:** 2026-09-14  
**Related:** [`ADR_005_USER_STORE_ASSIGNMENT.md`](ADR_005_USER_STORE_ASSIGNMENT.md) · [`MEMBERSHIP_REMAINING_GATE_MVP.md`](MEMBERSHIP_REMAINING_GATE_MVP.md)

## What landed

Engineering scaffold toward multi-store user assignment:

| Layer | Delivered |
|-------|-----------|
| Schema | `user_store_memberships` (`20260914_0113`) |
| Model | `UserStoreMembership` |
| Service | `backend/app/store_memberships.py` |
| APIs | `GET/POST/DELETE /stores/{id}/memberships`, `GET /me/store-memberships` |
| Flag | `STORE_MEMBERSHIP_SCOPE_ENABLED` default **false** (documented; not wired into scope) |
| Tests | `backend/tests/test_store_membership_scaffold.py` |

## What did **not** land

- Operational store scope still uses **`stores.manager_id`** via `dashboard_scope.managed_store_ids`
- Membership rows do **not** expand manager scope
- No store-scoped RBAC Complete
- No cashier POS store-picker UI Complete
- No claim of ADR-005 Complete

## Honesty flags (must stay false until cutover + verification)

```text
adr005_complete_claimed: false
store_scoped_rbac_complete_claimed: false
scope_wired_to_membership: false
scaffold_status: partial
operational_scope: stores.manager_id
```

Platform evidence `user_store_membership_claimed` remains **false**.

## Next cutover steps (separate Completes)

1. Optional admin UI to assign cashiers to stores
2. Explicit `managed_store_ids` cutover design (manager ∪ membership, or role-specific)
3. POS/session store lists from memberships where product requires it
4. Evidence pack + attestation before flipping any Complete flags

Offline Complete / 7-day VERIFIED / go-live / paid billing Completes remain **MISSING**.
