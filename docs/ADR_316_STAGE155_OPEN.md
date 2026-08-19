# ADR-316: Stage 155 Open — Tenant MVP Store Inventory CSV, Store Sales CSV & Product Warehouse-Stock CSV Export Fidelity

**Status:** Accepted  
**Date:** 2026-08-12  
**Related:** [ADR-315](ADR_315_STAGE154_FREEZE.md), [STAGE_155_PLAN.md](STAGE_155_PLAN.md)

## Context

Stage 154 closed PO amendments / product batches / API-key usage CSVs under ADR-315 and deferred **store inventory CSV**, **store sales CSV**, and **product warehouse-stock CSV**.
List handlers and UI panels already exist: store inventory/reorder, store sales (invoice+POS), and Inventory Stock warehouse placement (distinct from Stage 121 store/warehouse rosters and Stage 137 movements/low-stock/expiring).

## Decision

Open **Stage 155 — Tenant MVP Store Inventory CSV, Store Sales CSV & Product Warehouse-Stock CSV Export Fidelity** with packs:

| Pack | Scope |
|------|--------|
| **I1** | Store inventory: `GET /stores/{store_id}/inventory/export` + Stores Inventory / reorder Export inventory CSV |
| **S1** | Store sales: `GET /stores/{store_id}/sales/export` + Stores Sales Export sales CSV |
| **W1** | Product warehouse-stock: `GET /products/{product_id}/warehouse-stock/export` + Inventory Stock Export warehouse-stock CSV |
| **D1 / H155x** | Fidelity cite sync + Stage 155 exit; freeze as **ADR-317** |

## Consequences

- Completes store-scoped stock/commerce CSVs and per-product warehouse placement CSV.
- Does **not** claim ADR-002 billing Complete, fabricated MRR, ADR-005/003 Completes, impersonation, POS Hold/Resume, Stage 121/137 reopen, or main `ci.yml` deploy.
- Honesty flags stay false.
