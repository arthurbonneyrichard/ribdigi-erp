# ADR-314: Stage 154 Open — Tenant MVP PO Amendments CSV, Product Batches CSV & API-Key Usage CSV Export Fidelity

**Status:** Accepted  
**Date:** 2026-08-12  
**Related:** [ADR-313](ADR_313_STAGE153_FREEZE.md), [STAGE_154_PLAN.md](STAGE_154_PLAN.md)

## Context

Stage 153 closed tenant dashboard / party history CSVs under ADR-313 and deferred **PO amendments CSV**, **product batches CSV**, and **API-key usage CSV**.
List handlers and UI panels already exist: PO amendment history, per-product batches (distinct from Stage 137 expiring window), and API-key usage charts (distinct from Stage 127 keys roster).

## Decision

Open **Stage 154 — Tenant MVP PO Amendments CSV, Product Batches CSV & API-Key Usage CSV Export Fidelity** with packs:

| Pack | Scope |
|------|--------|
| **A1** | PO amendments: `GET /purchasing/orders/{id}/amendments/export` + Purchasing Export amendments CSV |
| **K1** | Product batches: `GET /products/{id}/batches/export` + Inventory Batches Export product batches CSV |
| **U1** | API-key usage: `GET /api-keys/{id}/usage/export` + Security Export usage CSV |
| **D1 / H154x** | Fidelity cite sync + Stage 154 exit; freeze as **ADR-315** |

## Consequences

- Completes purchase-order amendment ledger, per-product batch roster, and API-key usage series CSVs.
- Does **not** claim ADR-002 billing Complete, fabricated MRR, ADR-005/003 Completes, impersonation, POS Hold/Resume, API-key un-revoke, Stage 137 expiring reopen, Stage 127 keys roster reopen, or main `ci.yml` deploy.
- Honesty flags stay false.
