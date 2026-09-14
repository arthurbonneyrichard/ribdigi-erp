# ADR-005: User Store Assignment

**Status:** Accepted — **scaffold PARTIAL** (2026-09-14); Complete still **MISSING**  
**Date:** 2026-08-09  
**Scaffold:** [`ADR_005_MEMBERSHIP_SCAFFOLD.md`](ADR_005_MEMBERSHIP_SCAFFOLD.md)

## Context

BR-3.1 mentions branch/store assignment on users. Stage 1 already supports:

- User → `branch_id` / `department_id` (org assignment + record scopes)
- Store → `manager_id` (who manages a store)
- Store → linked warehouse (inventory location)

A dedicated User↔Store membership table (or `users.store_id`) would introduce a fourth org axis before Stage 1 scopes and reports need it.

## Decision

For Stage 1 / Commercial MVP operational scope:

1. **Operational store scope** remains **`stores.manager_id`** (and warehouse manager where set) via `dashboard_scope.managed_store_ids`.
2. Record scoping for users continues via **branch / department / own / all** (existing record_scope).
3. POS/sales store context remains **session/document `store_id`**, not a permanent user home store.
4. **Scaffold opened (PARTIAL):** `user_store_memberships` table + admin assign/list/revoke APIs + `GET /me/store-memberships` exist for assignment bookkeeping. These do **not** drive operational scope and do **not** equal ADR-005 Complete.
5. Multi-store membership scope cutover (membership-driven dashboards / cashier store lists wired into RBAC) remains **post-scaffold** until explicitly verified.

## Consequences

- BR-3.1 “branch/store assignment” is PARTIAL: branch (and department) yes; dedicated store assignment **scaffold PARTIAL** (table/API); scope cutover **MISSING**.
- Avoids parallel permission stacks: membership rows are assignment-only (no per-store permission JSON).
- Store managers remain editable on Multi-Store; membership admin APIs are company/tenant admin only (`store_manager` denied).
- Do **not** set `user_store_membership_claimed` / `adr005_complete_claimed` until scope cutover + evidence.

See also Stage 182 membership remaining-gate index: [`MEMBERSHIP_REMAINING_GATE_MVP.md`](MEMBERSHIP_REMAINING_GATE_MVP.md) (membership Complete remains deferred; scaffold ≠ Complete).
