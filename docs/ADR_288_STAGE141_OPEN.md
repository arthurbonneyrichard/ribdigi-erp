# ADR-288: Stage 141 Open — Tenant MVP Outstanding Bills CSV, Supplier Payment Schedule CSV & Party Statement CSV Export Fidelity

**Status:** Accepted  
**Date:** 2026-08-12  
**Related:** [ADR-287](ADR_287_STAGE140_FREEZE.md), [STAGE_141_PLAN.md](STAGE_141_PLAN.md)

## Context

Stage 140 closed ops settings CSVs under ADR-287.
Credit party-ops surfaces (**outstanding bills**, **supplier payment schedule**, **party statements**) already list for allocate/pay flows but lack `/export` (distinct from Stage 136 payment-register/aging CSVs).

## Decision

Open **Stage 141 — Tenant MVP Outstanding Bills CSV, Supplier Payment Schedule CSV & Party Statement CSV Export Fidelity** with packs:

| Pack | Scope |
|------|--------|
| **O1** | Outstanding bills CSV: `GET /customers|suppliers/{id}/outstanding/export` + Credit Export outstanding CSV |
| **P1** | Payment schedule CSV: `GET /suppliers/{id}/payment-schedule/export` + Credit Export schedule CSV |
| **T1** | Party statement CSV: `GET /credit/customers|suppliers/{id}/statement/export` + Credit Export statement CSV |
| **D1 / H141x** | Fidelity cite sync + Stage 141 exit; freeze as **ADR-289** |

## Consequences

- Completes Credit party-ops document CSVs after Stage 136 registers/aging.
- Does **not** reopen Stages 1–140; does **not** claim payment allocation line-dump Complete, ADR-002/005, ADR-003 hard-delete Complete, impersonation, or main `ci.yml` deploy.
