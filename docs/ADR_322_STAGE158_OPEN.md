# ADR-322: Stage 158 Open — Tenant MVP Dashboard Stock-Alerts CSV, Dashboard Expenses CSV & Dashboard Credit CSV Export Fidelity

**Status:** Accepted  
**Date:** 2026-08-12  
**Related:** [ADR-321](ADR_321_STAGE157_FREEZE.md), [STAGE_158_PLAN.md](STAGE_158_PLAN.md)

## Context

Stage 157 closed AI inventory predictions / sales-trend / top-products CSVs under ADR-321 and deferred **dashboard stock-alerts CSV**, **dashboard expenses CSV**, and **dashboard credit CSV**.
Slice handlers and Dashboard UI already exist: stock-alert KPIs, expenses-by-category, and AR outstanding (distinct from Stage 153 aggregates and Stage 157 chart/ranking slices).

## Decision

Open **Stage 158 — Tenant MVP Dashboard Stock-Alerts CSV, Dashboard Expenses CSV & Dashboard Credit CSV Export Fidelity** with packs:

| Pack | Scope |
|------|--------|
| **A1** | Stock-alerts: `GET /dashboard/stock-alerts/export` + Dashboard Export stock-alerts CSV |
| **E1** | Expenses: `GET /dashboard/expenses/export` + Dashboard Export expenses CSV |
| **C1** | Credit: `GET /dashboard/credit/export` + Dashboard Export credit CSV |
| **D1 / H158x** | Fidelity cite sync + Stage 158 exit; freeze as **ADR-323** |

## Consequences

- Completes remaining high-value dashboard KPI slice CSVs (stock / expenses / AR).
- Does **not** claim ADR-002 billing Complete, fabricated MRR, ADR-005/003 Completes, impersonation, POS Hold/Resume, Stage 153/157 reopen, or main `ci.yml` deploy.
- Honesty flags stay false.
