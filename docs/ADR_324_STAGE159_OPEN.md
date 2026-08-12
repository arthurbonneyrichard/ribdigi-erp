# ADR-324: Stage 159 Open — Tenant MVP Dashboard User-Stats CSV, Dashboard Summary CSV & Accounting Trial-Balance CSV Export Fidelity

**Status:** Accepted  
**Date:** 2026-08-12  
**Related:** [ADR-323](ADR_323_STAGE158_FREEZE.md), [STAGE_159_PLAN.md](STAGE_159_PLAN.md)

## Context

Stage 158 closed dashboard stock-alerts / expenses / credit CSVs under ADR-323 and deferred **dashboard user-stats CSV**, **dashboard summary CSV**, and **accounting trial-balance path CSV**.
Slice handlers and UI already exist: user-stats KPIs, compact summary KPIs, and accounting `#trial-balance` (path-scoped; distinct from Stage 153 aggregates, Stage 157/158 chart/KPI slices, and generic `/reports/export`).

## Decision

Open **Stage 159 — Tenant MVP Dashboard User-Stats CSV, Dashboard Summary CSV & Accounting Trial-Balance CSV Export Fidelity** with packs:

| Pack | Scope |
|------|--------|
| **U1** | User-stats: `GET /dashboard/user-stats/export` + Dashboard Export user-stats CSV |
| **M1** | Summary: `GET /dashboard/summary/export` + Dashboard Export summary CSV |
| **B1** | Trial-balance: `GET /accounting/trial-balance/export` + Accounting Export trial-balance CSV |
| **D1 / H159x** | Fidelity cite sync + Stage 159 exit; freeze as **ADR-325** |

## Consequences

- Completes remaining dashboard user-stats/summary slice CSVs and accounting path trial-balance CSV.
- Does **not** claim ADR-002 billing Complete, fabricated MRR, ADR-005/003 Completes, impersonation, POS Hold/Resume, Stage 153–158 reopen, `/reports/export` reopen, or main `ci.yml` deploy.
- Honesty flags stay false.
