# ADR-294: Stage 144 Open — Tenant MVP Webhook Deliveries CSV, Inventory FEFO Settings CSV & Audit Archives CSV Export Fidelity

**Status:** Accepted  
**Date:** 2026-08-12  
**Related:** [ADR-293](ADR_293_STAGE143_FREEZE.md), [STAGE_144_PLAN.md](STAGE_144_PLAN.md)

## Context

Stage 143 closed tenant bootstrap CSVs under ADR-293.
Compliance / ops surfaces (**webhook deliveries**, **inventory FEFO settings**, **audit cold archives**) list or configure in-product but lack dedicated `/export` CSVs (distinct from Stage 126 webhook *endpoints* CSV and hot `/audit-logs/export`).

## Decision

Open **Stage 144 — Tenant MVP Webhook Deliveries CSV, Inventory FEFO Settings CSV & Audit Archives CSV Export Fidelity** with packs:

| Pack | Scope |
|------|--------|
| **W1** | Webhook deliveries: `GET /webhooks/deliveries` + `/export` + Security `#webhooks` Export deliveries CSV (payload excluded) |
| **F1** | FEFO settings: `GET /inventory/settings/export` + Stores `#fefo` Export FEFO settings CSV |
| **A1** | Audit archives: `GET /audit-logs/archives/export` + Audit `#archives` Export archives CSV (no blob) |
| **D1 / H144x** | Fidelity cite sync + Stage 144 exit; freeze as **ADR-295** |

## Consequences

- Completes deliveries / FEFO / cold-archive CSVs after Stage 143 bootstrap CSVs.
- Does **not** reopen Stages 1–143; does **not** claim Stage 126 endpoints reopen, ADR-002/005, ADR-003 hard-delete Complete, impersonation, POS Hold/Resume, archive purge, or main `ci.yml` deploy.
