# ADR-308: Stage 151 Open — Tenant MVP Platform Health Checks CSV, Platform Operator Evidence CSV & Platform At-Risk Tenants CSV Export Fidelity

**Status:** Accepted  
**Date:** 2026-08-12  
**Related:** [ADR-307](ADR_307_STAGE150_FREEZE.md), [STAGE_151_PLAN.md](STAGE_151_PLAN.md)

## Context

Stage 150 closed plans / subscriptions / house settings commercial-metadata CSVs under ADR-307 and deferred **platform health checks CSV**.
Adjacent House ops surfaces (**operator evidence pack**, **at-risk tenants queue**) already list/JSON without dedicated `/export` CSVs — distinct from Stage 150 commercial metadata and Stage 149 staff identity exports.

## Decision

Open **Stage 151 — Tenant MVP Platform Health Checks CSV, Platform Operator Evidence CSV & Platform At-Risk Tenants CSV Export Fidelity** with packs:

| Pack | Scope |
|------|--------|
| **H1** | Health checks: `GET /platform/health/export` + Platform Health Export health CSV |
| **E1** | Operator evidence: `GET /platform/evidence/export` + Health UI Export evidence CSV |
| **A1** | At-risk tenants: `GET /platform/tenants/at-risk/export` + Tenants `#at-risk-queue` Export at-risk CSV |
| **D1 / H151x** | Fidelity cite sync + Stage 151 exit; freeze as **ADR-309** |

## Consequences

- Completes Stage 150 deferred platform health checks CSV and adjacent ops posture / risk-queue CSVs.
- Does **not** claim ADR-002 billing Complete, fabricated MRR, live subscriptions, checkout, ADR-005/003 Completes, impersonation, POS Hold/Resume, §§1–3/§7/go-live Completes, or main `ci.yml` deploy.
- Honesty flags stay false.
