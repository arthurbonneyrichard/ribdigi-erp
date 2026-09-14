# ADR-005 Membership Scaffold → Complete

**Status:** **Complete** (scaffold 2026-09-14; Complete attested 2026-09-15)  
**Related:** [`ADR_005_USER_STORE_ASSIGNMENT.md`](ADR_005_USER_STORE_ASSIGNMENT.md) · [`ADR_005_MEMBERSHIP_SCOPE_CUTOVER.md`](ADR_005_MEMBERSHIP_SCOPE_CUTOVER.md) · [`adr005_staging_soak_checklist.md`](adr005_staging_soak_checklist.md)

## Landed

Schema `user_store_memberships` · service `store_memberships.py` · assign/list/revoke + `/me/store-memberships` (visibility / `pos_store_bind_required`) · admin UI `/stores#memberships` · POS bind (`posStoreBinding.ts`) · flag `STORE_MEMBERSHIP_SCOPE_ENABLED` default **false** · automated soak `test_adr005_membership_scope_soak.py`.

## Complete criteria (SEC-M2 parallel)

| Criterion | Met? |
|-----------|------|
| Assignment CRUD + admin UI + `/me` | Yes |
| Flag-gated manager ∪ memberships + cashier fail-closed | Yes |
| POS store bind UX when scope ON | Yes |
| Automated flag-ON soak matrix | Yes |
| `adr005_complete_claimed` / `scope_wired_to_membership` | **true** |
| Production flag default ON | **No** — intentional ops |
| Store-scoped RBAC Complete | **No** — MISSING |

```text
adr005_complete_claimed: true
store_scoped_rbac_complete_claimed: false
scope_wired_to_membership: true
scaffold_status: complete
complete_means: feature_complete_plus_automated_flag_on_soak; production_default_flag_remains_off_until_ops_cutover
```

Offline / 7-day / go-live / paid billing Completes remain **MISSING**.
