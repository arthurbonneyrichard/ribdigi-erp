# ADR-282: Stage 138 Open — Tenant MVP Early-Pay Settings CSV, Expense Approval Settings CSV & Purchasing Approval Settings CSV Export Fidelity

**Status:** Accepted  
**Date:** 2026-08-12  
**Related:** [ADR-281](ADR_281_STAGE137_FREEZE.md), [STAGE_138_PLAN.md](STAGE_138_PLAN.md)

## Context

Stage 137 closed inventory ops-list CSVs under ADR-281.
Tenant admins can configure **early-pay terms**, **expense approval matrix**, and **purchasing PR approval matrix**, but cannot export those settings as CSV (email/SMS settings already ship secret-free exports; these three still lack `/export`).

## Decision

Open **Stage 138 — Tenant MVP Early-Pay Settings CSV, Expense Approval Settings CSV & Purchasing Approval Settings CSV Export Fidelity** with packs:

| Pack | Scope |
|------|--------|
| **C1** | Early-pay settings CSV: `GET /credit/settings/export` + Credit Export button |
| **E1** | Expense approval settings CSV: `GET /expenses/settings/export` + Expenses Export button |
| **P1** | Purchasing approval settings CSV: `GET /purchasing/settings/export` + Purchasing Export button |
| **D1 / H138x** | Fidelity cite sync + Stage 138 exit; freeze as **ADR-283** |

## Consequences

- Completes approval/settings CSV coverage after Stage 131 email and Stage 135 SMS.
- Does **not** reopen Stages 1–137; does **not** claim ADR-002/005, ADR-003 hard-delete Complete, impersonation, budgets/fiscal export, or main `ci.yml` deploy.
- Matrix levels are exported as compact `levels_json` (no secrets).
