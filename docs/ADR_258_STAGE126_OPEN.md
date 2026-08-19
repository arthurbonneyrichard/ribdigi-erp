# ADR-258: Stage 126 Open — Tenant MVP Inactive Bank Connections, Paused Webhooks & Bank/Webhook CSV Export Fidelity

**Status:** Accepted  
**Date:** 2026-08-12  
**Related:** [ADR-257](ADR_257_STAGE125_FREEZE.md), [STAGE_126_PLAN.md](STAGE_126_PLAN.md), [ADR-003](ADR_003_USER_DELETE_POLICY.md)

## Context

Stage 125 closed inactive liquid accounts, recurring expenses, and liquid/recurring CSV export under ADR-257.
Tenant operators still cannot filter inactive **bank feed connections** or **paused webhooks**, nor export them as CSV without secrets — leaving the bank-connector and webhook lifecycle incomplete. This was the Stage 125 deferred bank-connection / webhooks runner-up.

## Decision

Open **Stage 126 — Tenant MVP Inactive Bank Connections, Paused Webhooks & Bank/Webhook CSV Export Fidelity** with packs:

| Pack | Scope |
|------|--------|
| **C1** | Inactive bank connections: `GET/PATCH /accounting/bank-connections` `is_active`/`active_only`; Accounting filter + Deactivate/Reactivate; Shell Active/Inactive Bank Connections |
| **W1** | Paused webhooks: `GET /webhooks?is_active=` (+ `active_only`); Security Pause/Resume + filter; Shell Active/Paused Webhooks |
| **X1** | `GET /accounting/bank-connections/export` + `GET /webhooks/export` CSV (no secrets) + Export buttons |
| **D1 / H126x** | Fidelity cite sync + Stage 126 exit; freeze as **ADR-259** |

## Consequences

- Extends Stage 120–125 inactive + CSV patterns to bank connectors and webhooks.
- Does **not** reopen Stages 1–125; does **not** claim ADR-002/005, ADR-003 hard-delete Complete, impersonation, POS Hold/Resume, API-keys status+export, FX CSV, or main `ci.yml` deploy.
