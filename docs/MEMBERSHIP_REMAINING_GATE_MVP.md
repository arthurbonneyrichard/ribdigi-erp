# User↔Store Membership Remaining-Gate Index MVP — Stage 182 I1

**Status:** Complete (MVP packaging) — Stage 182 I1  
**Evidence:** `backend/tests/test_stage182_index_i1.py`  
**Register:** `ops/mvp/membership-remaining-gate.json`  
**Related:** [MEMBERSHIP_BLOCKERS_MVP.md](MEMBERSHIP_BLOCKERS_MVP.md) · [MEMBERSHIP_PACK_POINTERS_MVP.md](MEMBERSHIP_PACK_POINTERS_MVP.md) · [ADR_005_USER_STORE_ASSIGNMENT.md](ADR_005_USER_STORE_ASSIGNMENT.md) · [STAGE_182_PLAN.md](STAGE_182_PLAN.md)

Single index of user↔store membership remaining gates. Packaging only — **membership Complete remains MISSING.** Distinct from Stage 35 U1 / Stage 81 S1 packaging and Stage 181 billing remaining-gate index.

## Classification

| Flag | Value |
|------|-------|
| `packaging_complete` | true |
| `user_store_membership_claimed` | **false** |
| `users_store_id_api_claimed` | **false** |
| `multi_store_membership_claimed` | **false** |
| `store_scoped_rbac_complete_claimed` | **false** |
| `billing_complete_claimed` | **false** |
| `go_live_claimed` | **false** |

## Index order

1. Read **B1** blocker matrix (ADR-005, no `users.store_id`, store-scoped RBAC non-claim).
2. Follow **P1** pointers into ADR-005 / E2E users-RBAC / deferred ADR register / Stage 81 adjacency.
3. Reaffirm membership stays MISSING until a dedicated membership model is explicitly opened.
4. Do not treat Stage 35/81 packaging or `stores.manager_id` as membership Complete.
5. Leave membership / store_id API / multi-store membership as Remaining.

## Explicitly not claimed

- User↔store membership Complete
- `users.store_id` / membership API Completes
- Multi-store membership tables
- Billing / go-live Completes

See also Stage 183 hard-delete remaining-gate index: [`HARD_DELETE_REMAINING_GATE_MVP.md`](HARD_DELETE_REMAINING_GATE_MVP.md).
