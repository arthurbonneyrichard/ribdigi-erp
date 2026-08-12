# ADR-298: Stage 146 Open — Tenant MVP AI Low-Stock Prediction CSV, Demand Forecast CSV & Dead-Stock CSV Export Fidelity

**Status:** Accepted  
**Date:** 2026-08-12  
**Related:** [ADR-297](ADR_297_STAGE145_FREEZE.md), [STAGE_146_PLAN.md](STAGE_146_PLAN.md)

## Context

Stage 145 closed AI governance list CSVs under ADR-297.
Inventory AI prediction surfaces (**low-stock prediction**, **demand forecast**, **dead stock**) already list on `/ai` but lack dedicated `/export` CSVs (explicit Stage 145 Pack B runner-up).

## Decision

Open **Stage 146 — Tenant MVP AI Low-Stock Prediction CSV, Demand Forecast CSV & Dead-Stock CSV Export Fidelity** with packs:

| Pack | Scope |
|------|--------|
| **L1** | Low-stock prediction: `GET /ai/inventory/low-stock-prediction/export` + AI `#low-stock` Export low-stock CSV |
| **F1** | Demand forecast: `GET /ai/inventory/demand-forecast/export` + AI `#forecast` Export forecast CSV |
| **K1** | Dead stock: `GET /ai/inventory/dead-stock/export` + AI `#dead-stock` Export dead stock CSV |
| **D1 / H146x** | Fidelity cite sync + Stage 146 exit; freeze as **ADR-299** |

## Consequences

- Completes inventory AI prediction CSVs after Stage 145 governance CSVs.
- Does **not** reopen Stages 1–145; does **not** claim external LLM Complete, ADR-002/005, ADR-003 hard-delete Complete, impersonation, POS Hold/Resume, or main `ci.yml` deploy.
