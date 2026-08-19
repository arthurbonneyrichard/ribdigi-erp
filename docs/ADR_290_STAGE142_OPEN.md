# ADR-290: Stage 142 Open — Tenant MVP POS Sales Register CSV, Session Z-Report CSV & Store Cash Drawer Settings CSV Export Fidelity

**Status:** Accepted  
**Date:** 2026-08-12  
**Related:** [ADR-289](ADR_289_STAGE141_FREEZE.md), [STAGE_142_PLAN.md](STAGE_142_PLAN.md)

## Context

Stage 141 closed Credit party-ops CSVs under ADR-289.
POS commerce ops (**sales register**, **session Z-report**, **store cash drawer settings**) list/report in-product but lack dedicated `/export` CSVs (distinct from Stage 130 session inventory CSV).

## Decision

Open **Stage 142 — Tenant MVP POS Sales Register CSV, Session Z-Report CSV & Store Cash Drawer Settings CSV Export Fidelity** with packs:

| Pack | Scope |
|------|--------|
| **S1** | POS sales register: `GET /pos/sales` + `GET /pos/sales/export` + POS Export sales CSV |
| **Z1** | Session Z-report CSV: `GET /pos/sessions/{id}/report/export` + POS Export Z-report CSV |
| **C1** | Drawer settings CSV: `GET /stores/drawer-settings/export` + Stores `#cash-drawer` Export (kick bytes never included) |
| **D1 / H142x** | Fidelity cite sync + Stage 142 exit; freeze as **ADR-291** |

## Consequences

- Completes POS register / Z-report / drawer-config CSVs after Stage 130 sessions inventory.
- Does **not** reopen Stages 1–141; does **not** claim POS Hold/Resume, Stage 130 sessions reopen, ADR-002/005, ADR-003 hard-delete Complete, impersonation, or main `ci.yml` deploy.
