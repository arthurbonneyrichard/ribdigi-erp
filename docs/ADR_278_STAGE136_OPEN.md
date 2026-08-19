# ADR-278: Stage 136 Open — Tenant MVP Customer Payment Register CSV, Supplier Payment Register CSV & Credit Aging CSV Export Fidelity

**Status:** Accepted  
**Date:** 2026-08-12  
**Related:** [ADR-277](ADR_277_STAGE135_FREEZE.md), [STAGE_136_PLAN.md](STAGE_136_PLAN.md)

## Context

Stage 135 closed purchase-return / SMS / stores-transfer CSVs under ADR-277.
Tenant operators can **record** customer and supplier payments and view AR/AP aging, but cannot **list or export** payment registers or aging documents as CSV — payment tenant list APIs were explicitly deferred from Stage 135.

## Decision

Open **Stage 136 — Tenant MVP Customer Payment Register CSV, Supplier Payment Register CSV & Credit Aging CSV Export Fidelity** with packs:

| Pack | Scope |
|------|--------|
| **C1** | Customer payment register: `GET /credit/customer-payments` + `/export` (optional `customer_id`, `payment_method`) + Credit UI |
| **S1** | Supplier payment register: `GET /credit/supplier-payments` + `/export` (optional `supplier_id`, `payment_method`) + Credit UI |
| **A1** | Credit aging document CSV: `GET /credit/aging/export?kind=` + Credit Export aging CSV |
| **D1 / H136x** | Fidelity cite sync + Stage 136 exit; freeze as **ADR-279** |

## Consequences

- Completes credit payment-register and aging export after Stage 127 FX export and Stage 135 deferred payment lists.
- Does **not** reopen Stages 1–135; does **not** claim ADR-002/005, ADR-003 hard-delete Complete, impersonation, or main `ci.yml` deploy.
- Payment CSVs are **header-only** (no allocation line dump).
