# ADR-005 Membership → Scope Cutover Design (PARTIAL — not Complete)

**Status:** PARTIAL design + flag-gated wire (default **OFF**) + cashier POS/store-list fail-closed when flag ON  
**Date:** 2026-09-14  
**Related:** [`ADR_005_USER_STORE_ASSIGNMENT.md`](ADR_005_USER_STORE_ASSIGNMENT.md) · [`ADR_005_MEMBERSHIP_SCAFFOLD.md`](ADR_005_MEMBERSHIP_SCAFFOLD.md)

## Honesty (do not flip without evidence)

| Claim | State |
|-------|--------|
| ADR-005 Complete | **MISSING** |
| Store-scoped RBAC Complete | **MISSING** |
| Offline Complete / 7-day VERIFIED / go-live / paid billing Complete | **MISSING** |
| Production default uses membership scope | **No** — flag default `false` |
| `adr005_complete_claimed` / `scope_wired_to_membership` (Complete sense) | remain **false** |

This document + the flag-gated code path are **not** ADR-005 Complete. Ops must explicitly enable `STORE_MEMBERSHIP_SCOPE_ENABLED`; Completes require separate evidence.

---

## Goal

When enabled:

1. Operational store scope for **store_manager** includes active `user_store_memberships` store IDs in addition to `stores.manager_id`.
2. **Cashiers** are fail-closed on POS bind + store list surfaces onto active memberships (empty → denied / empty list).

Default (flag OFF) behavior is unchanged. Admin bypass and continuum store_manager redacts/denies are not weakened.

---

## Flag semantics

| Setting | Value | Behavior |
|---------|-------|----------|
| `STORE_MEMBERSHIP_SCOPE_ENABLED` | `false` (default) | Legacy: `managed_store_ids` uses **`stores.manager_id` only**. Cashiers stay company-wide on POS bind (`None`). Membership rows are assignment bookkeeping. |
| `STORE_MEMBERSHIP_SCOPE_ENABLED` | `true` | store_manager scope = **union** (below). Cashiers use **membership-only** fail-closed via `store_visibility_ids` (not `managed_store_ids`). |

- Enabling the flag does **not** set Complete honesty flags.
- Disabling the flag is the rollback switch (immediate return to legacy scope).
- Config: `backend/app/config.py` → env `STORE_MEMBERSHIP_SCOPE_ENABLED`.

---

## Composition rule (exact)

### Who is scoped via `managed_store_ids`?

`dashboard_scope.managed_store_ids` continues to apply only when
`dashboard_view_for_role(role) == "store_manager"`.

| Role / view | Flag OFF | Flag ON |
|-------------|----------|---------|
| `company_admin` / `super_admin` / `tenant_*` / `accountant` / other **executive** | `None` (tenant-wide; **admin bypass**) | `None` (unchanged bypass) |
| `cashier` | `None` | `None` (**unchanged** on this helper — see Cashier fail-closed) |
| `store_manager` | stores where `manager_id == user` ∧ `is_active` | **union** (below) |
| Missing `sub` / `tenant_id` | `[]` | `[]` |

### Union formula (flag ON, store_manager)

```text
managed = (
    { Store.id | Store.tenant_id = claims.tenant_id
                ∧ Store.manager_id = claims.sub
                ∧ Store.is_active }
  ∪
    { Membership.store_id | Membership.tenant_id = claims.tenant_id
                          ∧ Membership.user_id = claims.sub
                          ∧ Membership.is_active
                          ∧ Store.id = Membership.store_id
                          ∧ Store.tenant_id = claims.tenant_id
                          ∧ Store.is_active }
)
```

- **Union, not intersection.** A manager keeps every `manager_id` store even with no membership row; a membership row adds stores they do not manage via `manager_id`.
- Inactive memberships and inactive stores are **excluded**.
- Tenant isolation is mandatory on both legs.
- No company_id filter on this path (matches existing `manager_id` query).

### What is *not* changed by the flag for continuum

- RBAC module/action checks (`require_permission`, continuum redacts/denies keyed off `managed_ids is not None`).
- Membership **admin** APIs remain company/tenant-admin only (`store_manager` still 403).
- Warehouse scope still derives from `Warehouse.store_id ∈ managed_store_ids` (inherits expansion when flag ON for managers).
- Dual-manager transfer ship/receive still uses store `manager_id` person gates (not membership).

---

## Cashier fail-closed (POS + store lists)

Cashiers stay **`None` on `managed_store_ids`** so continuum company-level denies/redacts do not treat them as store_managers.

Fail-closed uses a dedicated path:

| Helper | Flag OFF | Flag ON (cashier) |
|--------|----------|-------------------|
| `managed_store_ids` | `None` | `None` |
| `cashier_membership_store_ids` | `None` (legacy) | membership IDs or `[]` |
| `store_visibility_ids` | `None` (legacy) | membership IDs or `[]` |

**Surfaces wired:**

- `GET /stores` (+ export / drawer-settings export) — empty list when no memberships
- `POST /pos/sessions/open` — `STORE_SCOPE_DENIED` when store missing / not in memberships / no memberships
- POS session list/export + session/sale asserts — same visibility scope

**Why not put cashiers onto `managed_store_ids`:** Continuum helpers treat `managed_ids is not None` as store_manager (company denies, receipt redacts, etc.). Cashier fail-closed must not inherit that matrix.

| Concern | store_manager | cashier |
|---------|---------------|---------|
| `managed_store_ids` | manager ∪ memberships (flag ON) | always `None` |
| POS / store list scope | via `store_visibility_ids` → managed | flag ON → membership fail-closed |
| Assignment visibility | `/me/store-memberships` | `/me/store-memberships` |

---

## Admin bypass

Roles whose dashboard view is not `store_manager` keep `managed_store_ids → None` (no store filter on continuum path). Membership rows never restrict admins. Membership **mutation** remains admin-gated regardless of flag.

---

## Rollback

1. Set `STORE_MEMBERSHIP_SCOPE_ENABLED=false` (or unset) and restart API workers.
2. Scope immediately reverts to `manager_id` only; cashier POS bind returns to company-wide; membership rows retained (no data delete).
3. No migration reverse required for this wire.

---

## Honesty payload (runtime)

| Field | Meaning after this slice |
|-------|--------------------------|
| `store_membership_scope_enabled` | Mirrors settings flag |
| `cashier_membership_fail_closed` | Mirrors settings flag (POS/store-list path active when true) |
| `operational_scope` | `stores.manager_id` when flag OFF; manager ∪ memberships + cashier fail-closed when flag ON |
| `scope_wired_to_membership` | Stays **false** until production-default cutover + Complete evidence |
| `adr005_complete_claimed` | **false** |
| `scaffold_status` | `partial` |

---

## Test matrix

| Case | Flag | Expect |
|------|------|--------|
| store_manager: manager store A, membership-only store B | OFF | A only |
| store_manager: manager A, membership B | ON | A ∪ B |
| store_manager: membership B only (no manager_id) | ON | B only |
| store_manager: inactive membership B | ON | B excluded |
| store_manager: membership on inactive store | ON | excluded |
| company_admin | ON | `managed_store_ids` `None` (bypass) |
| cashier | ON | `managed_store_ids` `None`; `store_visibility_ids` = memberships or `[]` |
| cashier POS open foreign / no membership | ON | 403 `STORE_SCOPE_DENIED` |
| cashier POS open / store list | OFF | legacy (no membership filter) |
| Honesty Complete flags | either | all false |
| Membership admin APIs as store_manager | either | 403 |

---

## Remaining before ADR-005 Complete

1. Ops enable flag in staging; soak + regression on store_manager + cashier POS surfaces.
2. POS store-picker UI Completes where product requires (Shell switcher still needs `stores:read`).
3. Evidence pack; only then consider flipping Complete honesty / production default.

Offline Complete / 7-day VERIFIED / go-live / paid billing Completes remain **MISSING**.
