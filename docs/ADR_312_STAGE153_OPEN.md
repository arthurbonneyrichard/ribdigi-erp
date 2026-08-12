# ADR-312: Stage 153 Open — Tenant MVP Tenant Dashboard Aggregates CSV, Customer History CSV & Supplier History CSV Export Fidelity

**Status:** Accepted  
**Date:** 2026-08-12  
**Related:** [ADR-311](ADR_311_STAGE152_FREEZE.md), [STAGE_153_PLAN.md](STAGE_153_PLAN.md)

## Context

Stage 152 closed platform dashboard / industries / permissions-matrix CSVs under ADR-311.
Tenant ERP still lacks **dashboard aggregates CSV** (platform mirror only) and party **activity history** CSVs — Stage 119 exported customer/supplier rosters, not history ledgers already loaded in Sales/Purchasing UI.

## Decision

Open **Stage 153 — Tenant MVP Tenant Dashboard Aggregates CSV, Customer History CSV & Supplier History CSV Export Fidelity** with packs:

| Pack | Scope |
|------|--------|
| **B1** | Tenant dashboard: `GET /dashboard/export` + Dashboard Export aggregates CSV |
| **C1** | Customer history: `GET /customers/{id}/history/export` + Sales Export history CSV |
| **S1** | Supplier history: `GET /suppliers/{id}/history/export` + Purchasing Export history CSV |
| **D1 / H153x** | Fidelity cite sync + Stage 153 exit; freeze as **ADR-313** |

## Consequences

- Completes tenant commercial ops KPI + party activity ledger CSVs.
- Does **not** claim ADR-002 billing Complete, fabricated MRR, ADR-005/003 Completes, impersonation, POS Hold/Resume, §§1–3/§7/go-live Completes, Stage 119 roster reopen, Stage 152 platform reopen, or main `ci.yml` deploy.
- Honesty flags stay false.
