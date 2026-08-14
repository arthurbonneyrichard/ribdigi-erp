# Store Membership Pack RG Blockers MVP — Stage 273 B1

**Status:** Complete (MVP packaging) — Stage 273 B1  
**Evidence:** `backend/tests/test_stage273_blockers_b1.py`  
**Register:** `ops/mvp/store-membership-pack-rg-blockers.json`  
**Related:** [STORE_MEMBERSHIP_PACK_REMAINING_GATE_MVP.md](STORE_MEMBERSHIP_PACK_REMAINING_GATE_MVP.md) · [ADR_005_USER_STORE_ASSIGNMENT.md](ADR_005_USER_STORE_ASSIGNMENT.md) · [MEMBERSHIP_REMAINING_GATE_MVP.md](MEMBERSHIP_REMAINING_GATE_MVP.md)

## Blockers

| ID | Surface | Status |
|----|---------|--------|
| store_membership_live | Live store-membership | REMAINING |
| users_store_id_complete | `users.store_id` | REMAINING |
| billing_complete | Paid billing | REMAINING |
| go_live_complete | Go-live | REMAINING |
| adr005_as_store_membership_complete | ADR-005 packaging as live store-membership Complete | NON_CLAIM |
| stage182_as_membership_complete | Stage 182 membership RG as Complete | NON_CLAIM |

Honesty: `store_membership_live_claimed` / `users_store_id_claimed` / `billing_complete_claimed` / `go_live_claimed` remain **false**.
