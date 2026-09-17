# ADR-005 Membership → Scope Cutover Design (**Complete**)

**Status:** **Complete** — flag-gated wire + cashier fail-closed + POS bind UX + automated flag-ON soak  
**Date:** 2026-09-14 (Complete attestation 2026-09-15)  
**Related:** [`ADR_005_USER_STORE_ASSIGNMENT.md`](ADR_005_USER_STORE_ASSIGNMENT.md) · [`ADR_005_MEMBERSHIP_SCAFFOLD.md`](ADR_005_MEMBERSHIP_SCAFFOLD.md) · [`adr005_staging_soak_checklist.md`](adr005_staging_soak_checklist.md)

## Honesty

| Claim | State |
|-------|--------|
| ADR-005 Complete | **Complete** (feature + automated soak) |
| Production default uses membership scope | **No** — flag default `false` (ops cutover) |
| `adr005_complete_claimed` / `scope_wired_to_membership` | **true** |
| `store_scoped_rbac_complete_claimed` | **false** |
| Offline Complete / 7-day VERIFIED / go-live / paid billing Complete | **MISSING** |

Complete means **feature complete + verified by automated flag-ON soak**, not
“flag already on in prod” — same pattern as SEC-M2 FIXED with cookie flag OFF.

## Flag semantics

| Setting | Behavior |
|---------|----------|
| `STORE_MEMBERSHIP_SCOPE_ENABLED=false` (default) | Legacy `manager_id` only; cashier POS company-wide |
| `STORE_MEMBERSHIP_SCOPE_ENABLED=true` | store_manager = manager_id ∪ memberships; cashier fail-closed via `store_visibility_ids` |

Union (flag ON, store_manager): active `manager_id` stores ∪ active memberships on active stores (tenant-isolated). Cashiers stay `None` on `managed_store_ids`. Admin bypass unchanged. Membership admin APIs remain company/tenant-admin only.

## POS bind

`/me/store-memberships` returns `store_visibility_ids` + `pos_store_bind_required`. POS UI (`posStoreBinding.ts`) requires in-scope `store_id` when visibility is a list.

## Test matrix evidence

`backend/tests/test_adr005_membership_scope_soak.py` · `test_store_membership_scaffold.py` · `frontend/lib/posStoreBinding.test.mjs` · `storeMembershipAdmin.test.mjs`

## Ops remaining after Complete

Staging/production enable of `STORE_MEMBERSHIP_SCOPE_ENABLED` per checklist.
Flag still false in prod examples is **intentional** — not unfinished wire.
