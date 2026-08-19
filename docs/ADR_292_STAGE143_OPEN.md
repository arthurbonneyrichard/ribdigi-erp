# ADR-292: Stage 143 Open — Tenant MVP Company Profile CSV, Jobs Catalog CSV & Onboarding Checklist CSV Export Fidelity

**Status:** Accepted  
**Date:** 2026-08-12  
**Related:** [ADR-291](ADR_291_STAGE142_FREEZE.md), [STAGE_143_PLAN.md](STAGE_143_PLAN.md)

## Context

Stage 142 closed POS commerce-ops CSVs under ADR-291.
Tenant bootstrap surfaces (**company profile**, **Celery jobs catalog**, **onboarding checklist**) already list/serialize in-product but lack dedicated `/export` CSVs (distinct from Stage 128 document settings and Stage 140 storage/backup settings).

## Decision

Open **Stage 143 — Tenant MVP Company Profile CSV, Jobs Catalog CSV & Onboarding Checklist CSV Export Fidelity** with packs:

| Pack | Scope |
|------|--------|
| **P1** | Company profile CSV: `GET /tenants/me/export` + Company `#profile` Export profile CSV |
| **J1** | Jobs catalog CSV: `GET /jobs/export` + Company `#jobs-catalog` Export (broker/result URLs never included) |
| **O1** | Onboarding checklist CSV: `GET /onboarding/checklist/export` + Shell Export checklist CSV |
| **D1 / H143x** | Fidelity cite sync + Stage 143 exit; freeze as **ADR-293** |

## Consequences

- Completes tenant bootstrap / ops-catalog CSVs after Stage 142 POS commerce CSVs.
- Does **not** reopen Stages 1–142; does **not** claim ADR-002 billing Complete, ADR-005 membership, ADR-003 hard-delete Complete, impersonation, POS Hold/Resume, Stage 128 document settings reopen, or main `ci.yml` deploy.
