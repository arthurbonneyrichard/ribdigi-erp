# ADR-270: Stage 132 Open — Tenant MVP Sales Invoice Register CSV, Stock-Transfer List Export & Purchase Invoice Register Fidelity

**Status:** Accepted  
**Date:** 2026-08-12  
**Related:** [ADR-269](ADR_269_STAGE131_FREEZE.md), [STAGE_132_PLAN.md](STAGE_132_PLAN.md)

## Context

Stage 131 closed journal CSV, bank statement status/CSV, and email-settings export under ADR-269.
Tenant operators still cannot export **sales invoice** or **purchase invoice** registers, or filter/export the **operational stock-transfer list** under inventory permissions — commerce document registers unused in Stages 120–131 (reports transfer history is a different permission surface).

## Decision

Open **Stage 132 — Tenant MVP Sales Invoice Register CSV, Stock-Transfer List Export & Purchase Invoice Register Fidelity** with packs:

| Pack | Scope |
|------|--------|
| **I1** | Sales invoice register CSV: `GET /sales/invoices/export` honoring status + Sales Export button |
| **T1** | Stock-transfer list status + CSV: `GET /inventory/stock-transfers?status=` + `/export`; Inventory filter + Shell Draft/Requested/In-transit/Received/Cancelled Warehouse Transfers |
| **P1** | Purchase invoice register CSV: `GET /purchasing/invoices/export` honoring status + Purchasing Export button |
| **D1 / H132x** | Fidelity cite sync + Stage 132 exit; freeze as **ADR-271** |

## Consequences

- Extends status-filter + CSV patterns to AR/AP invoice registers and inventory transfer ops lists.
- Does **not** reopen Stages 1–131; does **not** claim ADR-002/005, ADR-003 hard-delete Complete, impersonation, POS Hold/Resume, admin remote-revoke-others, or main `ci.yml` deploy.
- Invoice/transfer CSVs are **header-only** (no line dump).
