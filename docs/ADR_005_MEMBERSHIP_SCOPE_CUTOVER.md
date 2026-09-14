# ADR-005 Membership → Scope Cutover Design (PARTIAL — not Complete)

**Status:** PARTIAL design + flag-gated wire (default **OFF**)  
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

When enabled, operational store scope for **store_manager** includes active `user_store_memberships` store IDs in addition to `stores.manager_id`, without changing default (flag-OFF) behavior and without weakening admin bypass or RBAC.

---

## Flag semantics

| Setting | Value | Behavior |
|---------|-------|----------|
| `STORE_MEMBERSHIP_SCOPE_ENABLED` | `false` (default) | Legacy: `managed_store_ids` uses **`stores.manager_id` only**. Membership rows are assignment bookkeeping. |
| `STORE_MEMBERSHIP_SCOPE_ENABLED` | `true` | Cutover path: for `store_manager` only, scope = **union** of manager stores and active membership stores (see below). |

- Enabling the flag does **not** set Complete honesty flags.
- Disabling the flag is the rollback switch (immediate return to legacy scope).
- Config: `backend/app/config.py` → env `STORE_MEMBERSHIP_SCOPE_ENABLED`.

---

## Composition rule (exact)

### Who is scoped?

`dashboard_scope.managed_store_ids` continues to apply only when
`dashboard_view_for_role(role) == "store_manager"`.

| Role / view | Flag OFF | Flag ON |
|-------------|----------|---------|
| `company_admin` / `super_admin` / `tenant_*` / `accountant` / other **executive** | `None` (tenant-wide; **admin bypass**) | `None` (unchanged bypass) |
| `cashier` | `None` (not store-filtered via this helper) | `None` (unchanged this slice — see Cashier) |
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

### What is *not* changed by the flag

- RBAC module/action checks (`require_permission`, continuum redacts/denies).
- Membership **admin** APIs remain company/tenant-admin only (`store_manager` still 403).
- Warehouse scope still derives from `Warehouse.store_id ∈ managed_store_ids` (inherits expansion when flag ON).
- Dual-manager transfer ship/receive still uses store `manager_id` person gates (not membership).

---

## Cashier vs store_manager

| Concern | store_manager | cashier |
|---------|---------------|---------|
| `managed_store_ids` today | `manager_id` list | `None` (not filtered here) |
| Flag ON (this slice) | union expands list | **unchanged** (`None`) |
| Assignment visibility | `/me/store-memberships` | `/me/store-memberships` |
| POS store context | session / document `store_id` + managed asserts | session / document `store_id` |

**Why cashiers stay out of this wire:** Putting cashiers onto membership-only fail-closed lists would change company-wide vs empty-scope behavior for every consumer of `managed_store_ids`. That is a separate product decision (POS picker + fail-closed matrix) and must not ride this flag without its own evidence pack.

**Follow-on (not this slice):** optional cashier scope mode — when flag ON *and* a dedicated cashier cutover is attested, return membership IDs (or `[]` if none) instead of `None`.

---

## Admin bypass

Roles whose dashboard view is not `store_manager` keep `managed_store_ids → None` (no store filter). Membership rows never restrict admins. Membership **mutation** remains admin-gated regardless of flag.

---

## Rollback

1. Set `STORE_MEMBERSHIP_SCOPE_ENABLED=false` (or unset) and restart API workers.
2. Scope immediately reverts to `manager_id` only; membership rows retained (no data delete).
3. No migration reverse required for this wire.
4. If ops had provisioned cashiers expecting expansion: they were never expanded by this slice — no cashier rollback needed.

---

## Honesty payload (runtime)

| Field | Meaning after this slice |
|-------|--------------------------|
| `store_membership_scope_enabled` | Mirrors settings flag |
| `operational_scope` | `stores.manager_id` when flag OFF; `stores.manager_id ∪ user_store_memberships` when flag ON |
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
| company_admin | ON | `None` (bypass) |
| cashier | ON | `None` (unchanged) |
| Honesty Complete flags | either | all false |
| Membership admin APIs as store_manager | either | 403 |

---

## Remaining before ADR-005 Complete

1. Ops enable flag in staging; soak + regression on store_manager surfaces.
2. Decide/implement cashier membership fail-closed (if product requires).
3. POS store-picker Completes where needed.
4. Evidence pack; only then consider flipping Complete honesty / production default.

Offline Complete / 7-day VERIFIED / go-live / paid billing Completes remain **MISSING**.
