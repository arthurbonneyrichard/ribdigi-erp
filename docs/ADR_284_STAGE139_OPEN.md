# ADR-284: Stage 139 Open — Tenant MVP Expense Budgets CSV, Account Transactions CSV & Fiscal Period CSV Export Fidelity

**Status:** Accepted  
**Date:** 2026-08-12  
**Related:** [ADR-283](ADR_283_STAGE138_FREEZE.md), [STAGE_139_PLAN.md](STAGE_139_PLAN.md)

## Context

Stage 138 closed approval/settings CSVs under ADR-283.
Operators can view **expense budget variance**, **COA account ledger lines**, and **fiscal period close status**, but cannot export those surfaces as CSV (named deferred after Stage 138).

## Decision

Open **Stage 139 — Tenant MVP Expense Budgets CSV, Account Transactions CSV & Fiscal Period CSV Export Fidelity** with packs:

| Pack | Scope |
|------|--------|
| **B1** | Expense budgets CSV: `GET /expenses/budgets/export` + Expenses Export budgets CSV |
| **A1** | Account transactions CSV: `GET /accounting/accounts/{id}/transactions/export` + Accounting Export account ledger CSV |
| **F1** | Fiscal period CSV: `GET /accounting/fiscal-period/export` + Company Export fiscal period CSV |
| **D1 / H139x** | Fidelity cite sync + Stage 139 exit; freeze as **ADR-285** |

## Consequences

- Completes the finance ops-list CSV trio deferred after Stage 138.
- Does **not** reopen Stages 1–138; does **not** claim ADR-002/005, ADR-003 hard-delete Complete, impersonation, storage/notifications settings CSV, or main `ci.yml` deploy.
