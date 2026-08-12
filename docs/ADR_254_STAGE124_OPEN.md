# ADR-254: Stage 124 Open — Tenant MVP Inactive Product Variants, Custom Roles & Variant/Role CSV Export Fidelity

**Status:** Accepted  
**Date:** 2026-08-12  
**Related:** [ADR-253](ADR_253_STAGE123_FREEZE.md), [STAGE_124_PLAN.md](STAGE_124_PLAN.md), [ADR-003](ADR_003_USER_DELETE_POLICY.md)

## Context

Stage 123 closed inactive finance masters, customer groups, and finance/party-meta CSV export under ADR-253.
Tenant operators still cannot filter inactive **product variants** or inactive **custom roles**, nor export them as CSV — leaving catalog SKU lifecycle and RBAC role lifecycle incomplete relative to Stages 120–123 inactive/export fidelity.

## Decision

Open **Stage 124 — Tenant MVP Inactive Product Variants, Custom Roles & Variant/Role CSV Export Fidelity** with packs:

| Pack | Scope |
|------|--------|
| **V1** | Inactive product variants: `GET /products/{id}/variants?is_active=` / `active_only`; Inventory Variants Active/Inactive filter + Shell Active/Inactive Variants; Reactivate |
| **R1** | Inactive custom roles: `GET /roles?is_active=` / `active_only`; Admin Roles Active/Inactive filter + Deactivate/Reactivate + Shell Active/Inactive Custom Roles |
| **X1** | `GET /products/variants/export` + `GET /roles/export` CSV + Inventory/Admin Roles Export buttons |
| **D1 / H124x** | Fidelity cite sync + Stage 124 exit; freeze as **ADR-255** |

## Consequences

- Extends Stage 120–123 inactive + CSV patterns to variants and custom roles.
- Does **not** reopen Stages 1–123; does **not** claim ADR-002/005, ADR-003 hard-delete Complete, impersonation, POS Hold/Resume, or main `ci.yml` deploy.
- Soft-delete on unassigned custom roles remains; hard `DELETE` stays for unassigned customs only (ADR-003 Complete remains deferred).
