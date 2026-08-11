# Stage 83 Plan — Dual-Console Ops Fidelity

**Status:** Closed — exit met (H83x); freeze ADR-173  
**Base:** Store-Scoped Chart Depth + Tenant Admin User Ops → Dual-Console Ops Fidelity  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Open ADR (historical):** [ADR-172](ADR_172_STAGE83_OPEN.md)  
**Exit:** [STAGE_83_EXIT_CRITERIA.md](STAGE_83_EXIT_CRITERIA.md) · [ADR-173](ADR_173_STAGE83_FREEZE.md)  
**Prior freeze:** [ADR-171](ADR_171_STAGE82_FREEZE.md) · [STAGE_82_EXIT_CRITERIA.md](STAGE_82_EXIT_CRITERIA.md)

## Audit summary (pre-implementation)

Stage 82 closed tenant dashboard subroutes and Platform Plans. Remaining ops depth: chart/slice series still tenant-wide for Store Managers (KPI totals already scoped); Tenant Admin Users UI lacks reset-password and inline branch/department edit despite API support.

## Delivery packs (derived)

```
Store-Scoped Chart Depth Pack
        +
Tenant Admin User Ops Pack
        ↓
Dual-Console Ops Fidelity
```

## Delivery rules

1. One workstream at a time (full AC + automated tests before the next).
2. Prefer extending `dashboard_charts` / `dashboard_slices` / `/users` — do not invent parallel pages or membership tables.
3. No demo data / fake MRR.
4. After each feature: tests → commit → push → PR update.
5. Do not reopen Stage 1–82 feature scopes. Main `ci.yml` stays deploy-free (**Stage 18 C1**).
6. ADR-002 / ADR-005 remain deferred.

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **S1** | Store-scoped chart/slice depth (`managed_store_ids`) | P0 | COMPLETE |
| **U1** | Tenant Admin user-ops (reset password + org assignment edit) | P0 | COMPLETE |
| **D1** | Spec / readiness / launch / deploy / security fidelity sync | P1 | COMPLETE |
| **H83x** | Stage 83 exit criteria + freeze ADR | Exit | COMPLETE |

## Explicitly out of this pass

- Paid billing / fabricated MRR Complete (ADR-002)
- User↔Store membership table Complete (ADR-005)
- Dotted permission aliases
- Dedicated branch-assignments page
- Reopening Stages 80–82 frozen feature scopes
- Main `ci.yml` deploy jobs

## S1 acceptance criteria

- [x] `load_revenue_chart_series` accepts optional `store_ids`.
- [x] Main `/dashboard` + `/dashboard/sales-trend` + `/dashboard/top-products` honor managed stores for Store Managers.
- [x] Automated proof: `backend/tests/test_store_scoped_charts_s1.py`.

## U1 acceptance criteria

- [x] Users UI: reset password for existing users (wires `PATCH` password).
- [x] Users UI: inline branch/department assignment edit.
- [x] Automated proof: `backend/tests/test_admin_user_ops_u1.py`.

## D1 acceptance criteria

- [x] `docs/STAGE_83_FIDELITY.md` maps S1–U1 → readiness / launch / deploy / security.
- [x] Automated proof: `backend/tests/test_stage83_fidelity_d1.py`.

## H83x acceptance criteria

- [x] `docs/STAGE_83_EXIT_CRITERIA.md` + `docs/ADR_173_STAGE83_FREEZE.md`.
- [x] Automated proof: `backend/tests/test_stage83_exit_h83x.py`.
