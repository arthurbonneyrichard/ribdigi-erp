# ADR-318: Stage 156 Open — Tenant MVP Product Images CSV, Per-Product Variants CSV & Bank-Feed Settings CSV Export Fidelity

**Status:** Accepted  
**Date:** 2026-08-12  
**Related:** [ADR-317](ADR_317_STAGE155_FREEZE.md), [STAGE_156_PLAN.md](STAGE_156_PLAN.md)

## Context

Stage 155 closed store inventory / sales / warehouse-stock CSVs under ADR-317 and deferred **product images CSV**, **path-scoped per-product variants CSV**, and **bank-feed settings CSV**.
List handlers and UI surfaces already exist: product gallery images, per-product variants panel (distinct from Stage 124 tenant `/products/variants/export` roster), and `GET /settings/bank-feed` capability metadata (distinct from Stage 126 bank-connections export).

## Decision

Open **Stage 156 — Tenant MVP Product Images CSV, Per-Product Variants CSV & Bank-Feed Settings CSV Export Fidelity** with packs:

| Pack | Scope |
|------|--------|
| **G1** | Product images: `GET /products/{product_id}/images/export` + Inventory gallery Export images CSV |
| **V1** | Per-product variants: `GET /products/{product_id}/variants/export` + Inventory Variants Export product variants CSV |
| **F1** | Bank-feed settings: `GET /settings/bank-feed/export` + Accounting Export bank-feed settings CSV (secret-free) |
| **D1 / H156x** | Fidelity cite sync + Stage 156 exit; freeze as **ADR-319** |

## Consequences

- Completes gallery metadata, path-scoped variant, and bank-feed capability CSVs.
- Does **not** claim ADR-002 billing Complete, fabricated MRR, ADR-005/003 Completes, impersonation, POS Hold/Resume, Stage 124/126 reopen, or main `ci.yml` deploy.
- Honesty flags stay false.
