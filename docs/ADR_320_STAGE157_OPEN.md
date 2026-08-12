# ADR-320: Stage 157 Open — Tenant MVP AI Inventory Predictions CSV, Dashboard Sales-Trend CSV & Dashboard Top-Products CSV Export Fidelity

**Status:** Accepted  
**Date:** 2026-08-12  
**Related:** [ADR-319](ADR_319_STAGE156_FREEZE.md), [STAGE_157_PLAN.md](STAGE_157_PLAN.md)

## Context

Stage 156 closed product images / per-product variants / bank-feed settings CSVs under ADR-319 and deferred **combined AI inventory predictions CSV**, **dashboard sales-trend CSV**, and **dashboard top-products CSV**.
Handlers and UI surfaces already exist: `GET /ai/inventory/predictions` (combined forecast + low-stock), dashboard revenue series, and top-products ranking (distinct from Stage 146 F1/L1 dedicated exports and Stage 153 dashboard aggregates export).

## Decision

Open **Stage 157 — Tenant MVP AI Inventory Predictions CSV, Dashboard Sales-Trend CSV & Dashboard Top-Products CSV Export Fidelity** with packs:

| Pack | Scope |
|------|--------|
| **P1** | Combined predictions: `GET /ai/inventory/predictions/export` + AI Export predictions CSV |
| **S1** | Sales-trend: `GET /dashboard/sales-trend/export` + Dashboard Export sales-trend CSV |
| **T1** | Top-products: `GET /dashboard/top-products/export` + Dashboard Export top-products CSV |
| **D1 / H157x** | Fidelity cite sync + Stage 157 exit; freeze as **ADR-321** |

## Consequences

- Completes combined inventory intelligence CSV and dashboard chart/ranking slice CSVs.
- Does **not** claim ADR-002 billing Complete, fabricated MRR, ADR-005/003 Completes, impersonation, POS Hold/Resume, Stage 146/153 reopen, or main `ci.yml` deploy.
- Honesty flags stay false.
