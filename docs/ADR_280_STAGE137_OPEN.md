# ADR-280: Stage 137 Open — Tenant MVP Stock Movements CSV, Low-Stock Alert CSV & Expiring Batches CSV Export Fidelity

**Status:** Accepted  
**Date:** 2026-08-12  
**Related:** [ADR-279](ADR_279_STAGE136_FREEZE.md), [STAGE_137_PLAN.md](STAGE_137_PLAN.md)

## Context

Stage 136 closed credit payment registers and aging CSV under ADR-279.
Inventory operators can view **stock movements**, **low-stock alerts**, and **expiring batches**, but cannot export those operational lists as CSV (distinct from Reports packaging under `reports` permission).

## Decision

Open **Stage 137 — Tenant MVP Stock Movements CSV, Low-Stock Alert CSV & Expiring Batches CSV Export Fidelity** with packs:

| Pack | Scope |
|------|--------|
| **M1** | Stock movements CSV: `GET /inventory/movements/export` honoring existing filters + Inventory Export |
| **L1** | Low-stock alert CSV: `GET /inventory/low-stock?stock_status=` + `/export` + Inventory filter + Shell Red/Yellow leaves |
| **E1** | Expiring batches CSV: `GET /inventory/batches/expiring/export?days=` + Inventory Export + Shell 30/60/90 leaves |
| **D1 / H137x** | Fidelity cite sync + Stage 137 exit; freeze as **ADR-281** |

## Consequences

- Completes inventory ops-list CSV coverage after Stage 130 counts and Stage 132 transfers.
- Does **not** reopen Stages 1–136 or Reports `/reports/export`; does **not** claim ADR-002/005, ADR-003 hard-delete Complete, impersonation, or main `ci.yml` deploy.
