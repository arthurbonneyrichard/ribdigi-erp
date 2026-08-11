# Stage 80 Plan — Dual-Console Dashboard Fidelity

**Status:** Closed — exit met (H80x); freeze ADR-167  
**Base:** Platform Owner Dashboard Charts + Tenant Role-Scoped Dashboards → Dual-Console Dashboard Fidelity  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Open ADR (historical):** [ADR-166](ADR_166_STAGE80_OPEN.md)  
**Exit:** [STAGE_80_EXIT_CRITERIA.md](STAGE_80_EXIT_CRITERIA.md) · [ADR-167](ADR_167_STAGE80_FREEZE.md)  
**Prior freeze:** [ADR-165](ADR_165_STAGE79_FREEZE.md) · [STAGE_79_EXIT_CRITERIA.md](STAGE_79_EXIT_CRITERIA.md)

## Audit summary (pre-implementation)

Dual-console identity already ships under **ADR-137**: platform principal on reserved tenant `ribdigi-platform`, tenant ERP under `company_admin` (Tenant Admin) and operational roles. Stage 68 indexed House / Tenant consoles as honesty packaging. Gaps closed in this Stage: platform chart APIs/UI, role-scoped tenant dashboard views (cashier / store_manager / executive), backend permission-driven section filtering, dual-console security tests.

## Delivery packs (derived)

```
Platform Owner Dashboard Charts Pack
        +
Tenant Role-Scoped Dashboards Pack
        ↓
Dual-Console Dashboard Fidelity
```

## Delivery rules

1. One workstream at a time (full AC + automated tests before the next).
2. Prefer extending ADR-137 / existing `/dashboard` and `/platform/dashboard` — do not invent a parallel stack.
3. No demo data / fake MRR / fabricated chart series. Empty series when no rows.
4. After each feature: tests → commit → push → PR update.
5. Do not reopen Stage 1–79 feature scopes. Main `ci.yml` stays deploy-free (**Stage 18 C1**).
6. ADR-002 billing remains deferred.

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **P1** | Platform owner dashboard charts (real tenant growth / status / plan / industry / user growth; no fake MRR) | P0 | COMPLETE |
| **T1** | Tenant role-scoped dashboards + permission-driven sections (executive / store_manager / cashier) | P0 | COMPLETE |
| **D1** | Spec / readiness / launch / deploy / security fidelity sync | P1 | COMPLETE |
| **H80x** | Stage 80 exit criteria + freeze ADR | Exit | COMPLETE |

## Explicitly out of this pass

- Paid billing / fabricated MRR Complete (ADR-002)
- Inventing fake chart values
- Re-packaging Stage 68 House/Tenant honesty packs as new Complete
- Replacing ADR-137 principal model
- Main `ci.yml` deploy jobs
- Reopening Stages 1–79 frozen feature scopes

## P1 acceptance criteria

- [x] Platform chart series from real customer-tenant aggregates (growth, status, plan, industry, user growth).
- [x] APIs under `/api/v1/platform/dashboard/*` with `platform_dashboard:read`.
- [x] Platform dashboard UI renders charts; billing remains deferred (no fake MRR).
- [x] Automated proof: `backend/tests/test_platform_dashboard_charts_p1.py`.

## T1 acceptance criteria

- [x] Tenant `/dashboard` returns `view` (`executive` | `store_manager` | `cashier`) and `sections` filtered by permissions.
- [x] Cashier view omits accounting/purchasing/user-management aggregates.
- [x] Tenant Admin (`company_admin`) retains executive view + user stats when permitted.
- [x] Automated proof: `backend/tests/test_tenant_role_dashboard_t1.py`.

## D1 acceptance criteria

- [x] `docs/STAGE_80_FIDELITY.md` maps P1–T1 → readiness / launch / deploy / security.
- [x] Automated proof: `backend/tests/test_stage80_fidelity_d1.py`.

## H80x acceptance criteria

- [x] `docs/STAGE_80_EXIT_CRITERIA.md` + `docs/ADR_167_STAGE80_FREEZE.md`.
- [x] Automated proof: `backend/tests/test_stage80_exit_h80x.py`.
