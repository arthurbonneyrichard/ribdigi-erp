# ADR-266: Stage 130 Open — Tenant MVP Cheque Lifecycle CSV, POS Session Status & Stock-Count List Export Fidelity

**Status:** Accepted  
**Date:** 2026-08-12  
**Related:** [ADR-265](ADR_265_STAGE129_FREEZE.md), [STAGE_130_PLAN.md](STAGE_130_PLAN.md)

## Context

Stage 129 closed admin session inventory, notifications CSV, and backup job history export under ADR-265.
Tenant operators still cannot export the **cheque register**, filter/export **POS sessions** by open/closed status, or filter/export **stock-count list headers** — operational lifecycle lists unused in Stages 120–129.

## Decision

Open **Stage 130 — Tenant MVP Cheque Lifecycle CSV, POS Session Status & Stock-Count List Export Fidelity** with packs:

| Pack | Scope |
|------|--------|
| **C1** | Cheques CSV: `GET /accounting/cheques/export` honoring direction/status + Accounting Export button |
| **P1** | POS session status honesty + CSV: `GET /pos/sessions?status=open\|closed` + `/pos/sessions/export`; POS filter + Shell Open/Closed POS Sessions |
| **S1** | Stock-count list status + CSV: `GET /inventory/stock-counts?status=` + `/inventory/stock-counts/export`; Inventory filter + Shell Draft/Completed/Cancelled Stock Counts |
| **D1 / H130x** | Fidelity cite sync + Stage 130 exit; freeze as **ADR-267** |

## Consequences

- Extends status-filter + CSV patterns to cheque register, POS shifts, and stock-count headers.
- Does **not** reopen Stages 1–129; does **not** claim ADR-002/005, ADR-003 hard-delete Complete, impersonation, POS Hold/Resume, admin remote-revoke-others, or main `ci.yml` deploy.
