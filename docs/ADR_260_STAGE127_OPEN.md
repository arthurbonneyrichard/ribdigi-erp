# ADR-260: Stage 127 Open — Tenant MVP API-Key Status, FX Rates CSV & Report-Schedule CSV Export Fidelity

**Status:** Accepted  
**Date:** 2026-08-12  
**Related:** [ADR-259](ADR_259_STAGE126_FREEZE.md), [STAGE_127_PLAN.md](STAGE_127_PLAN.md)

## Context

Stage 126 closed inactive bank connections, paused webhooks, and bank/webhook CSV export under ADR-259.
Tenant operators still cannot filter API keys by **status** (active/revoked/expired), export API keys without secrets, export **FX rates**, or server-filter/export **report schedules** — the Stage 126 deferred runner-up trio.

## Decision

Open **Stage 127 — Tenant MVP API-Key Status, FX Rates CSV & Report-Schedule CSV Export Fidelity** with packs:

| Pack | Scope |
|------|--------|
| **K1** | API-key status honesty + CSV: `GET /api-keys?status=` / `active_only`; Security filter + Shell Active/Revoked/Expired API Keys; `GET /api-keys/export` (no secrets) |
| **F1** | FX rates CSV: `GET /credit/exchange-rates/export` + Credit Export button |
| **S1** | Report-schedule enabled filter + CSV: `GET /reports/schedules?enabled=` + `GET /reports/schedules/export` + Export button |
| **D1 / H127x** | Fidelity cite sync + Stage 127 exit; freeze as **ADR-261** |

## Consequences

- Extends status-filter + CSV patterns to API keys, FX, and report schedules.
- Does **not** reopen Stages 1–126; does **not** claim ADR-002/005, ADR-003 hard-delete Complete, impersonation, POS Hold/Resume, FX soft-delete, API-key un-revoke, or main `ci.yml` deploy.
