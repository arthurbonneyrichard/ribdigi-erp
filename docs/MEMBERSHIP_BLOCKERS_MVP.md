# User↔Store Membership Blocker Matrix MVP — Stage 182 B1

**Status:** Complete (MVP packaging) — Stage 182 B1  
**Evidence:** `backend/tests/test_stage182_blockers_b1.py`  
**Register:** `ops/mvp/membership-blockers.json`  
**Related:** [MEMBERSHIP_REMAINING_GATE_MVP.md](MEMBERSHIP_REMAINING_GATE_MVP.md) · [ADR_005_USER_STORE_ASSIGNMENT.md](ADR_005_USER_STORE_ASSIGNMENT.md) · [E2E_USERS_RBAC_MVP.md](E2E_USERS_RBAC_MVP.md) · [STAGE_182_PLAN.md](STAGE_182_PLAN.md)

Honest matrix of membership blockers. All listed gates remain Remaining / false / deferred.

## Classification

| Flag | Value |
|------|-------|
| `packaging_complete` | true |
| `user_store_membership_claimed` | **false** |
| `users_store_id_api_claimed` | **false** |
| `multi_store_membership_claimed` | **false** |
| `store_scoped_rbac_complete_claimed` | **false** |
| `go_live_claimed` | **false** |

## Blocker matrix

| Gate | Status | Notes |
|------|--------|-------|
| ADR-005 user↔store membership | Deferred | Branch/dept + `stores.manager_id` only |
| `users.store_id` / membership API | Remaining / false | No Stage 1 API |
| Multi-store membership table | Remaining / false | Post-Stage-1 if required |
| Store-scoped RBAC Completes as membership | Non-claim | Stage 81 `store_scope` ≠ ADR-005 membership |
| `user_store_membership_claimed` | **false** | Explicit non-claim |

## Explicitly not claimed

- Membership Complete because MVP packaging exists
- `users.store_id` API Completes from this matrix
- Store-scoped manager ops as membership Complete
