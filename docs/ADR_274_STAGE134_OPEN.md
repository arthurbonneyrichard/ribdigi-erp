# ADR-274: Stage 134 Open — Tenant MVP Purchase Request CSV, Purchase Order CSV & GRN CSV Export Fidelity

**Status:** Accepted  
**Date:** 2026-08-12  
**Related:** [ADR-273](ADR_273_STAGE133_FREEZE.md), [STAGE_134_PLAN.md](STAGE_134_PLAN.md)

## Context

Stage 133 closed sales quotation/order/return CSVs under ADR-273.
Tenant operators still cannot export the **purchasing pipeline** — purchase requests, purchase orders, and GRNs — despite existing status filters and Shell leaves (Stage 99 C1 / Stages 110+).

## Decision

Open **Stage 134 — Tenant MVP Purchase Request CSV, Purchase Order CSV & GRN CSV Export Fidelity** with packs:

| Pack | Scope |
|------|--------|
| **R1** | Purchase request CSV: `GET /purchasing/requests/export` honoring status + Purchasing Export button |
| **O1** | Purchase order CSV: `GET /purchasing/orders/export` honoring status + Purchasing Export button |
| **G1** | GRN CSV: `GET /purchasing/grn/export` honoring status + Purchasing Export button |
| **D1 / H134x** | Fidelity cite sync + Stage 134 exit; freeze as **ADR-275** |

## Consequences

- Completes purchasing document-register CSV coverage after Stage 132 invoices and Stage 133 sales pipeline.
- Does **not** reopen Stages 1–133; does **not** claim ADR-002/005, ADR-003 hard-delete Complete, impersonation, purchase-return CSV, payment lists, SMS settings CSV, or main `ci.yml` deploy.
- CSVs are **header-only** (no line dump).
