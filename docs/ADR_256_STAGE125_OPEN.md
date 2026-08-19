# ADR-256: Stage 125 Open — Tenant MVP Inactive Liquid Accounts, Recurring Expenses & Liquid/Recurring CSV Export Fidelity

**Status:** Accepted  
**Date:** 2026-08-12  
**Related:** [ADR-255](ADR_255_STAGE124_FREEZE.md), [STAGE_125_PLAN.md](STAGE_125_PLAN.md), [ADR-003](ADR_003_USER_DELETE_POLICY.md)

## Context

Stage 124 closed inactive product variants, custom roles, and variant/role CSV export under ADR-255.
Tenant operators still cannot filter inactive **liquid cash/bank accounts** or **paused recurring expenses**, nor export them as CSV with bank details — leaving the Cash & Bank / recurring lifecycle incomplete relative to Stages 120–124 inactive/export fidelity. This is the deferred liquid-bank-recurring cluster.

## Decision

Open **Stage 125 — Tenant MVP Inactive Liquid Accounts, Recurring Expenses & Liquid/Recurring CSV Export Fidelity** with packs:

| Pack | Scope |
|------|--------|
| **L1** | Inactive liquid accounts: `GET/PATCH /accounting/liquid-accounts` `is_active`/`active_only`; Accounting Cash & Bank filter + Deactivate/Reactivate; Shell Active/Inactive Liquid Accounts |
| **R1** | Paused recurring expenses: `GET /expenses/recurring?is_active=` (+ `active_only`); Expenses Recurring Pause/Resume + filter; Shell Active/Paused Recurring |
| **X1** | `GET /accounting/liquid-accounts/export` + `GET /expenses/recurring/export` CSV + Export buttons |
| **D1 / H125x** | Fidelity cite sync + Stage 125 exit; freeze as **ADR-257** |

## Consequences

- Extends Stage 120–124 inactive + CSV patterns to liquid accounts and recurring expenses.
- Does **not** reopen Stages 1–124; does **not** claim ADR-002/005, ADR-003 hard-delete Complete, impersonation, POS Hold/Resume, bank-connection export, or main `ci.yml` deploy.
