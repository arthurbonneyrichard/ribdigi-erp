# ADR-005 staging / ops membership-scope soak checklist

**Status:** ADR-005 remains **PARTIAL**. Automated flag-ON soak lives in
`backend/tests/test_adr005_membership_scope_soak.py`. This checklist is the
**operator** staging enable step — flag default remains
`STORE_MEMBERSHIP_SCOPE_ENABLED=false` in `.env.example` and
`.env.production.example`.

**Not claimed:** ADR-005 Complete · store-scoped RBAC Complete · Offline
Complete · 7-day VERIFIED · go-live · paid billing Complete.

Automated soak **≠** Complete. Do not flip production default to ON from this
checklist alone.

## Automated evidence (already landed)

| Check | Coverage |
|-------|----------|
| Flag default OFF (Settings + env examples) | `test_adr005_soak_flag_still_defaults_off_ops_enable` |
| Honesty Complete flags stay false | `test_adr005_soak_honesty_flags_never_complete` |
| Flag OFF legacy manager_id + cashier POS | `test_adr005_soak_flag_off_legacy_manager_and_cashier` |
| Flag ON store_manager union scope | `test_adr005_soak_flag_on_store_manager_union_scope` |
| Flag ON cashier with membership | `test_adr005_soak_flag_on_cashier_with_membership_only_assigned` |
| Flag ON cashier without membership empty/denied | `test_adr005_soak_flag_on_cashier_without_membership_empty_denied` |
| Flag ON admin bypass + mgr membership admin 403 | `test_adr005_soak_flag_on_admin_unaffected` |
| `/me/store-memberships` honesty under flag ON | `test_adr005_soak_me_memberships_honesty_flag_on` |
| Docs / checklist present | `test_adr005_soak_docs_and_checklist_present` |

Scaffold / fail-closed unit coverage remains in
`backend/tests/test_store_membership_scaffold.py`.

Run:

```bash
cd backend && .venv/bin/pytest \
  tests/test_adr005_membership_scope_soak.py \
  tests/test_store_membership_scaffold.py \
  -q
```

## Operator staging enable (cutover)

1. Staging env: set `STORE_MEMBERSHIP_SCOPE_ENABLED=true` and restart API workers
2. Confirm membership rows exist for cashiers who must open POS (`/stores#memberships`)
3. **store_manager:** login → `GET /stores` shows `manager_id` stores **plus**
   active membership stores only (not foreign stores)
4. **cashier with membership:** `GET /stores` shows only assigned stores; POS
   open succeeds on assigned store and returns `STORE_SCOPE_DENIED` on others
5. **cashier without membership:** `GET /stores` is empty; POS open denied
6. **company_admin / tenant admin:** still sees all company stores; can
   assign/revoke memberships; store_manager still cannot call membership admin APIs
7. `/me/store-memberships` shows `store_membership_scope_enabled: true` while
   `adr005_complete_claimed` / `scope_wired_to_membership` remain **false**
8. Rollback: set `STORE_MEMBERSHIP_SCOPE_ENABLED=false` and restart — legacy
   `manager_id`-only / company-wide cashier POS returns immediately (membership
   rows retained)
9. Only after staging soak evidence pack + product sign-off consider production
   enable — still does **not** by itself mark ADR-005 Complete

## Honesty

- Code path + automated soak keep ADR-005 **PARTIAL**.
- Leaving the flag OFF in production examples is intentional until ops completes
  this cutover with evidence.
- Do not treat “flag still false in prod” as unfinished wire after this soak —
  wire is flag-gated; Complete remains MISSING.
- Design: `docs/ADR_005_MEMBERSHIP_SCOPE_CUTOVER.md`
