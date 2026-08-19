# ADR-272: Stage 133 Open — Tenant MVP Sales Quotation CSV, Sales Order CSV & Sales Return CSV Export Fidelity

**Status:** Accepted  
**Date:** 2026-08-12  
**Related:** [ADR-271](ADR_271_STAGE132_FREEZE.md), [STAGE_133_PLAN.md](STAGE_133_PLAN.md)

## Context

Stage 132 closed sales/purchase invoice register CSVs and stock-transfer list export under ADR-271.
Tenant operators still cannot export the rest of the **sales pipeline** — quotations, orders, and returns — despite existing status filters and Shell leaves (Stages 98–99 / 109+).

## Decision

Open **Stage 133 — Tenant MVP Sales Quotation CSV, Sales Order CSV & Sales Return CSV Export Fidelity** with packs:

| Pack | Scope |
|------|--------|
| **Q1** | Sales quotation CSV: `GET /sales/quotations/export` honoring status + Sales Export button |
| **O1** | Sales order CSV: `GET /sales/orders/export` honoring status + Sales Export button |
| **R1** | Sales return CSV: `GET /sales/returns/export` honoring status + Sales Export button |
| **D1 / H133x** | Fidelity cite sync + Stage 133 exit; freeze as **ADR-273** |

## Consequences

- Completes sales document-register CSV coverage after Stage 132 invoices.
- Does **not** reopen Stages 1–132; does **not** claim ADR-002/005, ADR-003 hard-delete Complete, impersonation, POS Hold/Resume, purchasing pipeline CSVs, payment lists, or main `ci.yml` deploy.
- CSVs are **header-only** (no line dump).
