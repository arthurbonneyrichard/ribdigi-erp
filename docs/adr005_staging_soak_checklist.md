# ADR-005 staging / ops membership-scope soak checklist

**Status:** ADR-005 is **Complete** in code via automated flag-ON soak
(`backend/tests/test_adr005_membership_scope_soak.py`). This checklist is the
**operator** staging enable step — flag default remains
`STORE_MEMBERSHIP_SCOPE_ENABLED=false` in `.env.example` and
`.env.production.example`.

**Not claimed:** store-scoped RBAC Complete · Offline Complete · 7-day VERIFIED ·
go-live · paid billing Complete.

Automated soak **=** ADR-005 Complete evidence (SEC-M2 parallel). Do **not** flip
production default to ON from this checklist alone. Leaving the flag OFF does
**not** reopen ADR-005 Complete.

## Automated evidence

| Check | Coverage |
|-------|----------|
| Flag default OFF | `test_adr005_soak_flag_still_defaults_off_ops_enable` |
| Honesty Complete flags | `test_adr005_soak_honesty_complete_flags` |
| Flag OFF legacy | `test_adr005_soak_flag_off_legacy_manager_and_cashier` |
| Flag ON manager union | `test_adr005_soak_flag_on_store_manager_union_scope` |
| Flag ON manager membership-only | `test_adr005_soak_flag_on_store_manager_membership_only` |
| Flag ON cashier with membership | `test_adr005_soak_flag_on_cashier_with_membership_only_assigned` |
| Flag ON cashier empty/denied | `test_adr005_soak_flag_on_cashier_without_membership_empty_denied` |
| Flag ON admin bypass | `test_adr005_soak_flag_on_admin_unaffected` |
| `/me` visibility flag ON | `test_adr005_soak_me_memberships_honesty_and_visibility_flag_on` |
| `/me` no bind flag OFF | `test_adr005_soak_me_memberships_visibility_flag_off_no_bind` |
| Docs present | `test_adr005_soak_docs_and_checklist_present` |

```bash
cd backend && .venv/bin/pytest \
  tests/test_adr005_membership_scope_soak.py \
  tests/test_store_membership_scaffold.py -q
cd frontend && node --test lib/storeMembershipAdmin.test.mjs lib/posStoreBinding.test.mjs
```

## Operator staging enable (cutover)

1. Set `STORE_MEMBERSHIP_SCOPE_ENABLED=true`; restart API
2. Assign memberships at `/stores#memberships` for cashiers who must open POS
3. store_manager: sees manager_id ∪ memberships only
4. cashier with membership: assigned stores only; foreign POS → `STORE_SCOPE_DENIED`
5. cashier without membership: empty visibility; POS denied
6. admins bypass; store_manager cannot call membership admin APIs
7. `/me/store-memberships`: flag true, Complete honesty true, RBAC Complete false, `pos_store_bind_required` true
8. Rollback: set flag false — legacy returns; rows retained
9. Production enable is ops cutover — does not reopen ADR-005 Complete

## Honesty

- **ADR-005 = Complete** with automated soak evidence.
- Flag OFF in production examples is intentional until ops cutover.
- Design: `docs/ADR_005_MEMBERSHIP_SCOPE_CUTOVER.md`
