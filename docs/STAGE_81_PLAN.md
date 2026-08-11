# Stage 81 Plan — Dual-Console Admin Fidelity

**Status:** Closed — exit met (H81x); freeze ADR-169  
**Base:** Tenant Admin RBAC Console Surfaces + Store-Scoped Manager Ops → Dual-Console Admin Fidelity  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Open ADR (historical):** [ADR-168](ADR_168_STAGE81_OPEN.md)  
**Exit:** [STAGE_81_EXIT_CRITERIA.md](STAGE_81_EXIT_CRITERIA.md) · [ADR-169](ADR_169_STAGE81_FREEZE.md)  
**Prior freeze:** [ADR-167](ADR_167_STAGE80_FREEZE.md) · [STAGE_80_EXIT_CRITERIA.md](STAGE_80_EXIT_CRITERIA.md)

## Audit summary (pre-implementation)

Stage 80 closed platform charts and role-view labels. Remaining dual-console admin depth: Tenant Admin nav split (Users / Roles / Permissions), Store Manager KPI scoping via `stores.manager_id` (ADR-005 adjacency without membership table), and dual-console user mutation isolation tests.

## Delivery packs (derived)

```
Tenant Admin RBAC Console Surfaces Pack
        +
Store-Scoped Manager Ops Pack
        ↓
Dual-Console Admin Fidelity
```

## Delivery rules

1. One workstream at a time (full AC + automated tests before the next).
2. Prefer extending `/users`, Shell Admin group, `stores.manager_id`, and `_get_tenant_user` — do not invent parallel stacks.
3. No demo data / fake store metrics. Empty/zero when manager has no stores.
4. After each feature: tests → commit → push → PR update.
5. Do not reopen Stage 1–80 feature scopes. Main `ci.yml` stays deploy-free (**Stage 18 C1**).
6. ADR-002 billing and ADR-005 membership table remain deferred.

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **A1** | Tenant Admin RBAC console surfaces (Users / Roles / Permissions nav + pages) | P0 | COMPLETE |
| **S1** | Store-scoped manager dashboard ops + dual-console user isolation matrix | P0 | COMPLETE |
| **D1** | Spec / readiness / launch / deploy / security fidelity sync | P1 | COMPLETE |
| **H81x** | Stage 81 exit criteria + freeze ADR | Exit | COMPLETE |

## Explicitly out of this pass

- Paid billing / fabricated MRR Complete (ADR-002)
- User↔Store membership table Complete (ADR-005)
- Reopening Stage 80 platform/tenant chart packs
- Dedicated tenant chart subroutes
- Main `ci.yml` deploy jobs
- Reopening Stages 1–80 frozen feature scopes

## A1 acceptance criteria

- [x] Admin nav lists Users, Roles, Permissions (plus existing Audit/Backup/Security).
- [x] Dedicated `/admin/roles` and `/admin/permissions` surfaces; `/users` focused on user lifecycle + branch assignment.
- [x] Automated proof: `backend/tests/test_admin_console_a1.py`.

## S1 acceptance criteria

- [x] Store Manager dashboard includes `store_scope` derived from `stores.manager_id`.
- [x] Sales/expense KPIs aggregate only managed stores (not company-wide when scoped).
- [x] Isolation: foreign user PATCH/DELETE 404; tenant cannot create platform users; cashier cannot create users.
- [x] Automated proof: `backend/tests/test_store_scoped_manager_s1.py`.

## D1 acceptance criteria

- [x] `docs/STAGE_81_FIDELITY.md` maps A1–S1 → readiness / launch / deploy / security.
- [x] Automated proof: `backend/tests/test_stage81_fidelity_d1.py`.

## H81x acceptance criteria

- [x] `docs/STAGE_81_EXIT_CRITERIA.md` + `docs/ADR_169_STAGE81_FREEZE.md`.
- [x] Automated proof: `backend/tests/test_stage81_exit_h81x.py`.
