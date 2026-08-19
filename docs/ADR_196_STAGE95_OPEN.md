# ADR-196: Stage 95 Delivery Track Opened

**Status:** Accepted  
**Date:** 2026-08-12  
**Supersedes (in part):** ADR-195 clause that blocked opening the next delivery track until explicit sign-off

## Context

Stage 94 House Discovery & Runtime Assurance Ops exit criteria are met (`docs/STAGE_94_EXIT_CRITERIA.md`) with W1–T2 / D1 / H94x Complete (ADR-195). Product owner approved opening Stage 95 after Stage 94 freeze via CONTINUE/NEXT with a distinct product outline — the tenant **RIBDIGI ERP MVP Navigation** tree (Dashboard → Inventory → Stock → Sales → Purchase → Finance → People → Stores → Warehouse → Reports → User Management → Settings), not House platform ops:

```
Tenant Shell IA Regrouping
     ↓
Party & Stock Discoverability
     ↓
Chrome & Settings Alias Fidelity
     ↓
Tenant MVP Navigation Ops
```

Audit after Stage 94 found:

| Area | Status |
|------|--------|
| Commerce engines behind Inventory / Sales / Purchasing / Accounting / … | EXISTS (MVP Complete) |
| Flat Shell labels (Company, Multi-Store, Admin; no Finance/People sections) | PARTIAL vs MVP nav outline |
| Customers / Suppliers / Stock / Warehouse first-class discoverability | PARTIAL (nested tabs only) |
| Settings alias + profile/logout chrome + mobile nav collapse | MISSING / PARTIAL |
| Tab query write-back for deep-link honesty | PARTIAL (read-only `?tab=`) |
| Paid billing / membership / hard-delete / House Stage 94 reopen | DEFERRED / OUT |

## Decision

1. **Stage 95 delivery track is open** per `docs/STAGE_95_PLAN.md`.
2. **Stage 1–94 freezes remain** for their respective scopes (Stage 94 under ADR-195).
3. Deliver Stage 95 **one workstream at a time** (N1 → P1 → C1 → D1 → H95x).
4. Explicitly out of this pass: paid billing / fabricated MRR / checkout / `subscriptions_live_claimed` Complete (ADR-002); User↔Store membership Complete (ADR-005); hard-delete Complete (ADR-003); impersonation; claiming every MVP-nav leaf as a new page; reopening Stages 80–94 frozen scopes; main `ci.yml` deploy jobs; Ribdigi House / `PlatformShell` feature expansion. Honesty flags stay false: `mrr_fabricated_claimed: false`, `billing_complete_claimed: false`, `subscriptions_live_claimed: false`, `user_store_membership_claimed: false`, `hard_delete_claimed: false`, `sections_1_3_verified: false`, `section_7_signed: false`, `go_live_claimed: false`, `attestation_claimed: false`.
5. Extend proven `Shell.tsx`, `useTabQuery`, existing module pages — do not invent parallel nav stacks or duplicate CRUD surfaces.
6. Main `ci.yml` remains deploy-free (**Stage 18 C1**). Navigation IA packaging is honesty only — not every outline leaf Complete.

## Consequences

- Agents may implement Stage 95 plan items without reopening Stage 1–94 feature scope.
- Stage 95 exit requires `docs/STAGE_95_EXIT_CRITERIA.md` with no CRITICAL/MISSING rows for planned workstreams.
