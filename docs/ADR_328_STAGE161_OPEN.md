# ADR-328: Stage 161 Open — Tenant MVP Reports Profit-Loss Path CSV, Reports Trial-Balance Path CSV & Reports Tax Path CSV Export Fidelity

**Status:** Accepted  
**Date:** 2026-08-13  
**Related:** [ADR-327](ADR_327_STAGE160_FREEZE.md), [STAGE_161_PLAN.md](STAGE_161_PLAN.md)

## Context

Stage 160 closed accounting profit-loss and reports cash-flow / balance-sheet path CSVs under ADR-327. Remaining reports path siblings still MISSING: **`/reports/profit-loss/export`**, **`/reports/trial-balance/export`**, and **`/reports/tax/export`** (distinct from accounting path exports and generic `/reports/export`).

## Decision

Open **Stage 161 — Tenant MVP Reports Profit-Loss Path CSV, Reports Trial-Balance Path CSV & Reports Tax Path CSV Export Fidelity** with packs:

| Pack | Scope |
|------|--------|
| **L1** | Profit-loss: `GET /reports/profit-loss/export` + Reports Export profit-loss path CSV |
| **B1** | Trial-balance: `GET /reports/trial-balance/export` + Reports Export trial-balance path CSV |
| **X1** | Tax: `GET /reports/tax/export` + Reports/Tax Export tax path CSV |
| **D1 / H161x** | Fidelity cite sync + Stage 161 exit; freeze as **ADR-329** |

## Consequences

- Completes reports P&L / TB path pair and starts tax summary path CSV without reopening generic `/reports/export`.
- Does **not** claim ADR-002 billing Complete, fabricated MRR, ADR-005/003 Completes, impersonation, POS Hold/Resume, Stage 153–160 reopen, or main `ci.yml` deploy.
- Honesty flags stay false.
