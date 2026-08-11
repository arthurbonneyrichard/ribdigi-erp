# Stage 82 Plan — Dual-Console Surface Parity

**Status:** Closed — exit met (H82x); freeze ADR-171  
**Base:** Tenant Dashboard Chart Subroutes + Platform Plans Console → Dual-Console Surface Parity  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Open ADR (historical):** [ADR-170](ADR_170_STAGE82_OPEN.md)  
**Exit:** [STAGE_82_EXIT_CRITERIA.md](STAGE_82_EXIT_CRITERIA.md) · [ADR-171](ADR_171_STAGE82_FREEZE.md)  
**Prior freeze:** [ADR-169](ADR_169_STAGE81_FREEZE.md) · [STAGE_81_EXIT_CRITERIA.md](STAGE_81_EXIT_CRITERIA.md)

## Audit summary (pre-implementation)

Stage 81 closed Admin nav split and store-manager KPI scoping. Remaining dual-console surface parity: tenant dashboard chart/KPI subroutes (platform already has chart subroutes), Platform Plans metadata console (not paid billing), and Admin Activity→Audit alias.

## Delivery packs (derived)

```
Tenant Dashboard Chart Subroutes Pack
        +
Platform Plans Console Pack
        ↓
Dual-Console Surface Parity
```

## Delivery rules

1. One workstream at a time (full AC + automated tests before the next).
2. Prefer extending `/dashboard`, `dashboard_views`, and existing `plan_code` PATCH — do not invent payment collection.
3. No demo data / fake MRR. Plan codes remain metadata (ADR-002).
4. After each feature: tests → commit → push → PR update.
5. Do not reopen Stage 1–81 feature scopes. Main `ci.yml` stays deploy-free (**Stage 18 C1**).
6. ADR-002 / ADR-005 remain deferred.

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **C1** | Tenant dashboard chart/KPI subroutes (permission-filtered) | P0 | COMPLETE |
| **P1** | Platform Plans console + Admin Activity alias | P0 | COMPLETE |
| **D1** | Spec / readiness / launch / deploy / security fidelity sync | P1 | COMPLETE |
| **H82x** | Stage 82 exit criteria + freeze ADR | Exit | COMPLETE |

## Explicitly out of this pass

- Paid billing / fabricated MRR Complete (ADR-002)
- User↔Store membership table Complete (ADR-005)
- Reopening Stage 80 platform chart packs
- Reopening Stage 81 A1/S1 scopes
- Main `ci.yml` deploy jobs
- Reopening Stages 1–81 frozen feature scopes

## C1 acceptance criteria

- [x] Subroutes: `/dashboard/summary`, `/sales-trend`, `/top-products`, `/expenses`, `/stock-alerts`, `/user-stats`.
- [x] Tenant scope from auth identity; permission filter via `dashboard_views`.
- [x] Automated proof: `backend/tests/test_dashboard_slices_c1.py`.

## P1 acceptance criteria

- [x] `GET /platform/plans` catalog (metadata; billing deferred).
- [x] `/platform/plans` UI + PlatformShell Plans nav.
- [x] Tenant Admin Activity alias (`/activity` → audit surface).
- [x] Automated proof: `backend/tests/test_platform_plans_p1.py`.

## D1 acceptance criteria

- [x] `docs/STAGE_82_FIDELITY.md` maps C1–P1 → readiness / launch / deploy / security.
- [x] Automated proof: `backend/tests/test_stage82_fidelity_d1.py`.

## H82x acceptance criteria

- [x] `docs/STAGE_82_EXIT_CRITERIA.md` + `docs/ADR_171_STAGE82_FREEZE.md`.
- [x] Automated proof: `backend/tests/test_stage82_exit_h82x.py`.
