# Stage 89 Plan — House Customer Assist & Roster Intelligence Ops

**Status:** Closed — exit met (H89x); freeze ADR-185  
**Base:** House Tenant Admin Assist + Tenant Roster Filters & Dashboard At-Risk KPIs + Plan Catalog & Billing Roster Depth → House Customer Assist & Roster Intelligence Ops  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Open ADR (historical):** [ADR-184](ADR_184_STAGE89_OPEN.md)  
**Exit:** [STAGE_89_EXIT_CRITERIA.md](STAGE_89_EXIT_CRITERIA.md) · freeze [ADR-185](ADR_185_STAGE89_FREEZE.md)  
**Fidelity:** [STAGE_89_FIDELITY.md](STAGE_89_FIDELITY.md)  
**Prior freeze:** [ADR-183](ADR_183_STAGE88_FREEZE.md) · [STAGE_88_EXIT_CRITERIA.md](STAGE_88_EXIT_CRITERIA.md)

## Delivery packs (derived)

```
House Tenant Admin Assist Pack
        +
Tenant Roster Filters & Dashboard At-Risk KPIs Pack
        +
Plan Catalog & Billing Roster Depth Pack
        ↓
House Customer Assist & Roster Intelligence Ops
```

## Delivery rules

1. One workstream at a time (full AC + automated tests before the next).
2. Prefer extending AuthToken email flows, list filters, plan metadata, dashboard KPIs — do not invent parallel consoles.
3. No demo data / fake MRR. No impersonation into customer ERP.
4. After each feature: tests → commit → push → PR update.
5. Do not reopen Stage 1–88 feature scopes. Main `ci.yml` stays deploy-free (**Stage 18 C1**).
6. ADR-002 / ADR-005 remain deferred; ADR-003 stays soft-delete-only (`hard_delete_claimed: false`).

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **A1** | House Tenant Admin assist (password-reset + resend verify) | P0 | COMPLETE |
| **F1** | Roster plan/industry filters + dashboard grace/at-risk KPIs | P0 | COMPLETE |
| **C1** | Plan catalog metadata + billing roster depth | P0 | COMPLETE |
| **D1** | Spec / readiness / launch / deploy / security fidelity sync | P1 | COMPLETE |
| **H89x** | Stage 89 exit criteria + freeze ADR | Exit | COMPLETE |

## Explicitly out of this pass

- Paid billing / fabricated MRR / checkout / `subscriptions_live_claimed` Complete (ADR-002)
- User↔Store membership Complete (ADR-005)
- Hard-delete archival Complete (ADR-003)
- Impersonation into customer ERP
- Reopening Stages 80–88 frozen feature scopes
- Main `ci.yml` deploy jobs

## A1 acceptance criteria

- [x] `POST /platform/tenants/{id}/admin/password-reset-email` and `…/admin/resend-verification` for that tenant’s `company_admin`; detail UI; audited; no impersonation.
- [x] Automated proof: `backend/tests/test_platform_tenant_admin_assist_a1.py`.

## F1 acceptance criteria

- [x] `plan_code` + `industry` filters on tenant list/export; dashboard grace + at-risk KPI cards with deep-link.
- [x] Automated proof: `backend/tests/test_platform_roster_intel_f1.py`.

## C1 acceptance criteria

- [x] `/platform/plans` catalog labels/blurbs/soft limits (no prices); Plans UI table; Billing roster `trial_ends_at` + tenant deep-links; honesty flags false.
- [x] Automated proof: `backend/tests/test_platform_catalog_billing_c1.py`.

## D1 acceptance criteria

- [x] `docs/STAGE_89_FIDELITY.md` maps A1–C1 → readiness / launch / deploy / security.
- [x] Automated proof: `backend/tests/test_stage89_fidelity_d1.py`.

## H89x acceptance criteria

- [x] `docs/STAGE_89_EXIT_CRITERIA.md` + `docs/ADR_185_STAGE89_FREEZE.md`.
- [x] Automated proof: `backend/tests/test_stage89_exit_h89x.py`.
