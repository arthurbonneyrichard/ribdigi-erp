# ADR-296: Stage 145 Open — Tenant MVP AI Security Alerts CSV, Report Templates CSV & Business Insights CSV Export Fidelity

**Status:** Accepted  
**Date:** 2026-08-12  
**Related:** [ADR-295](ADR_295_STAGE144_FREEZE.md), [STAGE_145_PLAN.md](STAGE_145_PLAN.md)

## Context

Stage 144 closed compliance/ops CSVs under ADR-295.
AI governance surfaces (**security alerts**, **report templates**, **business insights**) already list on `/ai` but lack dedicated `/export` CSVs (distinct from inventory AI prediction surfaces and Stage 144).

## Decision

Open **Stage 145 — Tenant MVP AI Security Alerts CSV, Report Templates CSV & Business Insights CSV Export Fidelity** with packs:

| Pack | Scope |
|------|--------|
| **S1** | Security alerts: `GET /ai/security/alerts/export` + AI `#security` Export security alerts CSV |
| **T1** | Report templates: `GET /ai/reports/templates/export` + AI `#report-generator` Export templates CSV |
| **I1** | Business insights: `GET /ai/insights/export` + AI `#insights` Export insights CSV |
| **D1 / H145x** | Fidelity cite sync + Stage 145 exit; freeze as **ADR-297** |

## Consequences

- Completes AI list-catalog CSVs after Stage 144 compliance CSVs.
- Does **not** reopen Stages 1–144; does **not** claim inventory AI prediction CSVs (Pack B runner-up), LLM Complete, ADR-002/005, ADR-003 hard-delete Complete, impersonation, POS Hold/Resume, or main `ci.yml` deploy.
