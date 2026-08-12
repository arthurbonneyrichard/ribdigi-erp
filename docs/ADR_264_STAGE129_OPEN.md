# ADR-264: Stage 129 Open — Tenant MVP Admin Session Inventory, Notifications CSV & Backup-Job History Export Fidelity

**Status:** Accepted  
**Date:** 2026-08-12  
**Related:** [ADR-263](ADR_263_STAGE128_FREEZE.md), [STAGE_129_PLAN.md](STAGE_129_PLAN.md)

## Context

Stage 128 closed caller-only session status/CSV, passkey inventory CSV, and document-settings CSV under ADR-263.
Tenant operators still lack **tenant-wide admin session inventory**, **notifications CSV**, and **backup job status filter/CSV** — the Stage 128 deferred runner-up trio (admin sessions) plus ops list surfaces that filter but never exported.

## Decision

Open **Stage 129 — Tenant MVP Admin Session Inventory, Notifications CSV & Backup-Job History Export Fidelity** with packs:

| Pack | Scope |
|------|--------|
| **A1** | Tenant-wide admin session inventory: `GET /auth/tenant-sessions?status=` / `active_only`; Security Tenant sessions UI + Shell Tenant Active/Revoked Sessions; `GET /auth/tenant-sessions/export` (no refresh-token secrets) |
| **N1** | Notifications CSV: `GET /notifications/export` honoring status/group/category + Notifications Export button |
| **B1** | Backup job status filter + CSV: `GET /backup?status=` + `GET /backup/export` (metadata only) + Backup UI/Shell Completed/Failed Backups |
| **D1 / H129x** | Fidelity cite sync + Stage 129 exit; freeze as **ADR-265** |

## Consequences

- Extends status-filter + CSV patterns to admin session inventory, notifications, and backup job history.
- Does **not** reopen Stages 1–128; does **not** claim ADR-002/005, ADR-003 hard-delete Complete, impersonation, POS Hold/Resume, admin remote-revoke-others, API-key un-revoke, FX soft-delete, or main `ci.yml` deploy.
