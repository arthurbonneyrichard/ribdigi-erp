# ADR-262: Stage 128 Open — Tenant MVP Session Status, Passkey Inventory CSV & Document-Numbering CSV Export Fidelity

**Status:** Accepted  
**Date:** 2026-08-12  
**Related:** [ADR-261](ADR_261_STAGE127_FREEZE.md), [STAGE_128_PLAN.md](STAGE_128_PLAN.md)

## Context

Stage 127 closed API-key status honesty, FX rates CSV, and report-schedule enabled filter/CSV under ADR-261.
Tenant operators still cannot filter **auth sessions** by status, export **session** or **passkey** inventories without secrets, or export **document numbering / print template** settings — the Stage 127 deferred runner-up trio.

## Decision

Open **Stage 128 — Tenant MVP Session Status, Passkey Inventory CSV & Document-Numbering CSV Export Fidelity** with packs:

| Pack | Scope |
|------|--------|
| **S1** | Session status honesty + CSV: `GET /auth/sessions?status=` / `active_only`; Security filter + Shell Active/Revoked Sessions; `GET /auth/sessions/export` (no refresh-token secrets) |
| **P1** | Passkey inventory CSV: `GET /auth/webauthn/credentials/export` (no public_key / credential_id) + Security Export button |
| **N1** | Document numbering + print template settings CSV: `GET /tenants/me/document-settings/export` + Company Export button |
| **D1 / H128x** | Fidelity cite sync + Stage 128 exit; freeze as **ADR-263** |

## Consequences

- Extends status-filter + CSV patterns to sessions, passkeys, and company document settings.
- Does **not** reopen Stages 1–127; does **not** claim ADR-002/005, ADR-003 hard-delete Complete, impersonation, POS Hold/Resume, API-key un-revoke, FX soft-delete, tenant-wide admin session inventory, or main `ci.yml` deploy.
