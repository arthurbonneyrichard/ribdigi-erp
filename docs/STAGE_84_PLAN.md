# Stage 84 Plan — Dual-Console Permission & Slice Fidelity

**Status:** Closed — exit met (H84x); freeze ADR-175  
**Base:** Dotted Permission Aliases + Tenant Dashboard Slice Depth → Dual-Console Permission & Slice Fidelity  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Open ADR (historical):** [ADR-174](ADR_174_STAGE84_OPEN.md)  
**Exit:** [STAGE_84_EXIT_CRITERIA.md](STAGE_84_EXIT_CRITERIA.md) · [ADR-175](ADR_175_STAGE84_FREEZE.md)  
**Prior freeze:** [ADR-173](ADR_173_STAGE83_FREEZE.md) · [STAGE_83_EXIT_CRITERIA.md](STAGE_83_EXIT_CRITERIA.md)

## Audit summary (pre-implementation)

Stage 83 closed store-scoped charts and Tenant Admin user-ops. Remaining dual-console fidelity: dotted permission aliases still deferred; expenses slice lacks by-category breakdown; credit section has permissions but no `SECTION_FIELDS`; cashier open-shift status is API-only.

## Delivery packs (derived)

```
Dotted Permission Aliases Pack
        +
Tenant Dashboard Slice Depth Pack (+ cashier polish)
        ↓
Dual-Console Permission & Slice Fidelity
```

## Delivery rules

1. One workstream at a time (full AC + automated tests before the next).
2. Prefer extending `rbac` / `dashboard_slices` / `dashboard_views` / existing `/pos/sessions/current` — do not invent parallel permission engines or dashboards.
3. No demo data / fake MRR.
4. After each feature: tests → commit → push → PR update.
5. Do not reopen Stage 1–83 feature scopes. Main `ci.yml` stays deploy-free (**Stage 18 C1**).
6. ADR-002 / ADR-005 remain deferred.

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **A1** | Dotted permission aliases (`view`→`read`; `module.action` / `module:action`) | P0 | COMPLETE |
| **S1** | Expenses-by-category + credit outstanding slices; cashier open-shift UI | P0 | COMPLETE |
| **D1** | Spec / readiness / launch / deploy / security fidelity sync | P1 | COMPLETE |
| **H84x** | Stage 84 exit criteria + freeze ADR | Exit | COMPLETE |

## Explicitly out of this pass

- Paid billing / fabricated MRR Complete (ADR-002)
- User↔Store membership table Complete (ADR-005)
- Admin email-initiated password reset
- Platform subscriptions roster as billing Complete
- Reopening Stages 80–83 frozen feature scopes
- Main `ci.yml` deploy jobs

## A1 acceptance criteria

- [x] `normalize_permissions_map` accepts action alias `view`→`read` and dotted/colon keys (`inventory.view`, `inventory:read`).
- [x] `has_permission` honors aliases on overrides / action argument.
- [x] Automated proof: `backend/tests/test_permission_aliases_a1.py`.

## S1 acceptance criteria

- [x] Expenses slice includes `expenses_by_category`; credit slice exposes outstanding AR; `SECTION_FIELDS` includes credit (+ expenses category fields).
- [x] Cashier dashboard UI shows open-shift status via `GET /pos/sessions/current`.
- [x] Automated proof: `backend/tests/test_dashboard_slice_depth_s1.py`.

## D1 acceptance criteria

- [x] `docs/STAGE_84_FIDELITY.md` maps A1–S1 → readiness / launch / deploy / security.
- [x] Automated proof: `backend/tests/test_stage84_fidelity_d1.py`.

## H84x acceptance criteria

- [x] `docs/STAGE_84_EXIT_CRITERIA.md` + `docs/ADR_175_STAGE84_FREEZE.md`.
- [x] Automated proof: `backend/tests/test_stage84_exit_h84x.py`.
