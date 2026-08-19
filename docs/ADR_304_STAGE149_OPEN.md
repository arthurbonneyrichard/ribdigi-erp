# ADR-304: Stage 149 Open — Tenant MVP AI Document Analyze CSV, Platform Staff Users CSV & Platform Staff Sessions CSV Export Fidelity

**Status:** Accepted  
**Date:** 2026-08-12  
**Related:** [ADR-303](ADR_303_STAGE148_FREEZE.md), [STAGE_149_PLAN.md](STAGE_149_PLAN.md)

## Context

Stage 148 closed assistant / customer / cross-domain AI CSVs under ADR-303 and deferred **document analyze list CSV**.
Platform staff roster and sessions list on `/platform/users` without dedicated `/export` CSVs (distinct from Stages 145–148 tenant AI exports and from Stage 88/120 tenant user exports).

## Decision

Open **Stage 149 — Tenant MVP AI Document Analyze CSV, Platform Staff Users CSV & Platform Staff Sessions CSV Export Fidelity** with packs:

| Pack | Scope |
|------|--------|
| **A1** | Document analyze: `POST /ai/documents/analyze/export` + AI `#document` Export analyze CSV |
| **U1** | Platform staff users: `GET /platform/users/export` + Platform Users Export users CSV |
| **S1** | Platform staff sessions: `GET /platform/users/sessions/export` + Export sessions CSV |
| **D1 / H149x** | Fidelity cite sync + Stage 149 exit; freeze as **ADR-305** |

## Consequences

- Completes Stage 148 deferred document analyze CSV and opens platform staff CSV exports.
- Does **not** reopen Stages 1–148; does **not** claim external LLM Complete, ADR-002/005, ADR-003 hard-delete Complete, impersonation, POS Hold/Resume, platform plans CSV, or main `ci.yml` deploy.
