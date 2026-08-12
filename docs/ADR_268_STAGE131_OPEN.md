# ADR-268: Stage 131 Open — Tenant MVP Journal Entry CSV, Bank Statement Status & Email-Settings Export Fidelity

**Status:** Accepted  
**Date:** 2026-08-12  
**Related:** [ADR-267](ADR_267_STAGE130_FREEZE.md), [STAGE_131_PLAN.md](STAGE_131_PLAN.md)

## Context

Stage 130 closed cheque lifecycle CSV, POS session status/CSV, and stock-count list export under ADR-267.
Tenant operators still cannot export **journal entry headers**, filter/export **bank statements** by draft/in_progress/reconciled status, or export **email/SMTP settings** without secrets — finance ops lists unused in Stages 120–130.

## Decision

Open **Stage 131 — Tenant MVP Journal Entry CSV, Bank Statement Status & Email-Settings Export Fidelity** with packs:

| Pack | Scope |
|------|--------|
| **J1** | Journal entry header CSV: `GET /accounting/journal-entries/export` honoring status/store_id + Accounting Export button |
| **B1** | Bank statement status honesty + CSV: `GET /accounting/bank-statements?status=draft\|in_progress\|reconciled` + `/export`; UI filter + Shell Draft/In Progress/Reconciled Statements |
| **E1** | Email settings CSV: `GET /settings/email/export` (secret-free; `has_password` only) + Company Email Export button |
| **D1 / H131x** | Fidelity cite sync + Stage 131 exit; freeze as **ADR-269** |

## Consequences

- Extends status-filter + CSV patterns to journals, bank statement headers, and email settings metadata.
- Does **not** reopen Stages 1–130; does **not** claim ADR-002/005, ADR-003 hard-delete Complete, impersonation, POS Hold/Resume, admin remote-revoke-others, or main `ci.yml` deploy.
- SMTP password is never exported.
