# ADR-326: Stage 160 Open — Tenant MVP Accounting Profit-Loss CSV, Reports Cash-Flow Path CSV & Reports Balance-Sheet Path CSV Export Fidelity

**Status:** Accepted  
**Date:** 2026-08-12  
**Related:** [ADR-325](ADR_325_STAGE159_FREEZE.md), [STAGE_160_PLAN.md](STAGE_160_PLAN.md)

## Context

Stage 159 closed dashboard user-stats / summary and accounting trial-balance path CSVs under ADR-325 and deferred **accounting profit-loss path CSV** plus remaining distinct financial statement path exports.
Handlers and UI already exist: Accounting `#profit-loss`, Reports cash-flow / balance-sheet tabs (path-scoped GETs; distinct from Stage 159 trial-balance and generic `/reports/export`).

## Decision

Open **Stage 160 — Tenant MVP Accounting Profit-Loss CSV, Reports Cash-Flow Path CSV & Reports Balance-Sheet Path CSV Export Fidelity** with packs:

| Pack | Scope |
|------|--------|
| **P1** | Profit-loss: `GET /accounting/profit-loss/export` + Accounting Export profit-loss CSV |
| **C1** | Cash-flow: `GET /reports/cash-flow/export` + Reports Export cash-flow path CSV |
| **S1** | Balance-sheet: `GET /reports/balance-sheet/export` + Reports Export balance-sheet path CSV |
| **D1 / H160x** | Fidelity cite sync + Stage 160 exit; freeze as **ADR-327** |

## Consequences

- Completes remaining high-value financial statement path CSVs without reopening generic `/reports/export`.
- Does **not** claim ADR-002 billing Complete, fabricated MRR, ADR-005/003 Completes, impersonation, POS Hold/Resume, Stage 153–159 reopen, or main `ci.yml` deploy.
- Honesty flags stay false.
