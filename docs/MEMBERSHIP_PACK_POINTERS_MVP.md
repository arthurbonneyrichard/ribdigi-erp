# User↔Store Membership Pack Pointers MVP — Stage 182 P1

**Status:** Complete (MVP packaging) — Stage 182 P1  
**Evidence:** `backend/tests/test_stage182_pointers_p1.py`  
**Register:** `ops/mvp/membership-pack-pointers.json`  
**Related:** [MEMBERSHIP_REMAINING_GATE_MVP.md](MEMBERSHIP_REMAINING_GATE_MVP.md) · [ADR_005_USER_STORE_ASSIGNMENT.md](ADR_005_USER_STORE_ASSIGNMENT.md) · [E2E_USERS_RBAC_MVP.md](E2E_USERS_RBAC_MVP.md) · [DEFERRED_ADR_REGISTER_MVP.md](DEFERRED_ADR_REGISTER_MVP.md) · [BILLING_REMAINING_GATE_MVP.md](BILLING_REMAINING_GATE_MVP.md) · [STAGE_182_PLAN.md](STAGE_182_PLAN.md)

Pointers into ADR-005, E2E users/RBAC, deferred ADR register, and Stage 181 billing remaining-gate adjacency. Every pointer keeps membership non-claimed.

## Classification

| Flag | Value |
|------|-------|
| `packaging_complete` | true |
| `user_store_membership_claimed` | **false** |
| `users_store_id_api_claimed` | **false** |
| `store_membership_claimed` | **false** |
| `go_live_claimed` | **false** |

## Pack pointers

| Gate theme | Primary docs |
|------------|--------------|
| ADR-005 user store assignment | `ADR_005_USER_STORE_ASSIGNMENT.md` |
| E2E users + RBAC honesty | `E2E_USERS_RBAC_MVP.md` / `ops/mvp/e2e-users-rbac.json` |
| Deferred ADR register | `DEFERRED_ADR_REGISTER_MVP.md` |
| Stage 81 store_scope adjacency | `PRODUCTION_READINESS.md` / `test_store_scoped_manager_s1.py` |
| Stage 181 billing remaining-gate | `BILLING_REMAINING_GATE_MVP.md` (orthogonal deferred) |

## Explicit non-claim

1. Stage 35 U1 / Stage 81 S1 packaging Completes are **not** membership Complete.
2. ADR-005 keeps dedicated membership deferred.
3. `stores.manager_id` / branch-dept scopes are not user↔store membership.
4. Do not claim membership Complete from this pointer index.

## Explicitly not claimed

- User↔store membership / `users.store_id` Completes
- Multi-store membership Completes
- Billing / go-live Completes
