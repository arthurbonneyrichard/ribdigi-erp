# ADR-005 Membership Scaffold (PARTIAL — not Complete)

**Status:** PARTIAL scaffold  
**Date:** 2026-09-14  
**Related:** [`ADR_005_USER_STORE_ASSIGNMENT.md`](ADR_005_USER_STORE_ASSIGNMENT.md) · [`ADR_005_MEMBERSHIP_SCOPE_CUTOVER.md`](ADR_005_MEMBERSHIP_SCOPE_CUTOVER.md) · [`MEMBERSHIP_REMAINING_GATE_MVP.md`](MEMBERSHIP_REMAINING_GATE_MVP.md)

## What landed

Engineering scaffold toward multi-store user assignment:

| Layer | Delivered |
|-------|-----------|
| Schema | `user_store_memberships` (`20260914_0113`) |
| Model | `UserStoreMembership` |
| Service | `backend/app/store_memberships.py` |
| APIs | `GET/POST/DELETE /stores/{id}/memberships`, `GET /me/store-memberships` |
| Admin UI | `/stores#memberships` — Company/Admin list/assign/remove (`StoreMembershipAdmin`; hidden for `store_manager` / API 403) |
| Flag | `STORE_MEMBERSHIP_SCOPE_ENABLED` default **false** |
| Cutover design | [`ADR_005_MEMBERSHIP_SCOPE_CUTOVER.md`](ADR_005_MEMBERSHIP_SCOPE_CUTOVER.md) |
| Flag-gated wire | When flag **true**, `managed_store_ids` = `manager_id` ∪ active memberships (**store_manager** only); default OFF = legacy |
| Tests | `backend/tests/test_store_membership_scaffold.py`; `frontend/lib/storeMembershipAdmin.test.mjs` |

## What did **not** land

- Production default still uses **`stores.manager_id` only** (flag OFF)
- Flag ON is **not** ADR-005 Complete / not store-scoped RBAC Complete
- Cashier still not fail-closed onto membership via `managed_store_ids`
- No cashier POS store-picker UI Complete
- No claim of ADR-005 Complete

## Honesty flags (must stay false until production-default cutover + verification)

```text
adr005_complete_claimed: false
store_scoped_rbac_complete_claimed: false
scope_wired_to_membership: false
scaffold_status: partial
operational_scope: stores.manager_id   # or ∪ memberships when flag ON (runtime)
```

Platform evidence `user_store_membership_claimed` remains **false**.

## Next cutover steps (separate Completes)

1. Staging soak with flag ON + regression evidence
2. Cashier membership fail-closed decision (if product requires)
3. POS/session store lists from memberships where product requires it
4. Evidence pack + attestation before flipping Complete flags / production default

Offline Complete / 7-day VERIFIED / go-live / paid billing Completes remain **MISSING**.
