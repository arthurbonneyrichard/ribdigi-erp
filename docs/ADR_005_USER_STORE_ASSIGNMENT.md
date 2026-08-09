# ADR-005: User Store Assignment Deferred

**Status:** Accepted  
**Date:** 2026-08-09

## Context

BR-3.1 mentions branch/store assignment on users. Stage 1 already supports:

- User → `branch_id` / `department_id` (org assignment + record scopes)
- Store → `manager_id` (who manages a store)
- Store → linked warehouse (inventory location)

A dedicated User↔Store membership table (or `users.store_id`) would introduce a fourth org axis before Stage 1 scopes and reports need it.

## Decision

For Stage 1 / Commercial MVP:

1. **No `users.store_id` / user–store membership API** in Stage 1.
2. Store responsibility is modeled by **`stores.manager_id`** (and warehouse manager where set).
3. Record scoping for users continues via **branch / department / own / all** (existing record_scope).
4. POS/sales store context remains **session/document `store_id`**, not a permanent user home store.
5. Multi-store user membership (one user assigned to many stores for scoped dashboards) is **post-Stage-1** if required.

## Consequences

- BR-3.1 “branch/store assignment” is PARTIAL: branch (and department) yes; dedicated store assignment deferred.
- Avoids parallel permission stacks and FK complexity during Stage 1 freeze.
- Store managers remain editable on Multi-Store (Stage 1 C8).
