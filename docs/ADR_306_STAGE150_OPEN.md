# ADR-306: Stage 150 Open — Tenant MVP Platform Plans Catalog CSV, Platform Subscriptions Roster CSV & Platform House Settings CSV Export Fidelity

**Status:** Accepted  
**Date:** 2026-08-12  
**Related:** [ADR-305](ADR_305_STAGE149_FREEZE.md), [STAGE_150_PLAN.md](STAGE_150_PLAN.md)

## Context

Stage 149 closed document analyze + platform staff CSVs under ADR-305 and deferred **platform plans catalog CSV**.
Adjacent House console surfaces (**subscriptions roster**, **house settings**) list without dedicated `/export` CSVs — distinct from Stage 149 staff identity exports and from Stages 145–148 tenant AI exports.

## Decision

Open **Stage 150 — Tenant MVP Platform Plans Catalog CSV, Platform Subscriptions Roster CSV & Platform House Settings CSV Export Fidelity** with packs:

| Pack | Scope |
|------|--------|
| **P1** | Plans catalog: `GET /platform/plans/export` + Platform Plans Export plans CSV |
| **R1** | Subscriptions roster: `GET /platform/subscriptions/export` + Billing Export subscriptions CSV |
| **S1** | House settings: `GET /platform/settings/export` + Platform Settings Export settings CSV |
| **D1 / H150x** | Fidelity cite sync + Stage 150 exit; freeze as **ADR-307** |

## Consequences

- Completes Stage 149 deferred plans catalog CSV and adjacent commercial-metadata / house settings CSVs.
- Does **not** claim ADR-002 billing Complete, fabricated MRR, live subscriptions, checkout, ADR-005/003 Completes, impersonation, POS Hold/Resume, platform health CSV, or main `ci.yml` deploy.
- Honesty flags stay false.
