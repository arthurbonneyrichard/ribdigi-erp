# ADR-198: Stage 96 Delivery Track Opened

**Status:** Accepted  
**Date:** 2026-08-12  
**Supersedes (in part):** ADR-197 clause that blocked opening the next delivery track until explicit sign-off

## Context

Stage 95 Tenant MVP Navigation Ops exit criteria are met (`docs/STAGE_95_EXIT_CRITERIA.md`) with N1–C1 / D1 / H95x Complete (ADR-197). Product owner approved opening Stage 96 after Stage 95 freeze via CONTINUE/NEXT with a distinct product outline — remaining **MVP Navigation outline surface fidelity** (Dashboard Business Overview, global topbar search, Finance/Sales/Settings leaf discoverability), not another Shell IA regroup:

```
Dashboard Business Overview Fidelity
     ↓
Global Topbar Search
     ↓
Finance / Sales / Settings Leaf Fidelity
     ↓
Tenant MVP Outline Surface Fidelity Ops
```

Audit after Stage 95 found:

| Area | Status |
|------|--------|
| Shell IA / party-stock deep-links / chrome aliases | EXISTS (Stage 95 frozen) |
| Dashboard Profit Summary / AP Payables / notification deep-links | MISSING / PARTIAL |
| Global topbar search | MISSING (Stage 95 deferred) |
| Money Transfer / Income / Billers / Delivery Status / Settings leaf aliases | PARTIAL / MISSING |
| Paid billing / membership / hard-delete / House reopen | DEFERRED / OUT |

## Decision

1. **Stage 96 delivery track is open** per `docs/STAGE_96_PLAN.md`.
2. **Stage 1–95 freezes remain** for their respective scopes (Stage 95 under ADR-197).
3. Deliver Stage 96 **one workstream at a time** (B1 → G1 → L1 → D1 → H96x).
4. Explicitly out of this pass: paid billing / fabricated MRR / checkout / `subscriptions_live_claimed` Complete (ADR-002); User↔Store membership Complete (ADR-005); hard-delete Complete (ADR-003); impersonation; full Billers CRUD engine; parallel Income approval module; WYSIWYG document designer; reopening Stages 80–95 frozen scopes (including Stage 95 Shell IA); main `ci.yml` deploy jobs; Ribdigi House / `PlatformShell` feature expansion. Honesty flags stay false: `mrr_fabricated_claimed: false`, `billing_complete_claimed: false`, `subscriptions_live_claimed: false`, `user_store_membership_claimed: false`, `hard_delete_claimed: false`, `sections_1_3_verified: false`, `section_7_signed: false`, `go_live_claimed: false`, `attestation_claimed: false`.
5. Extend proven dashboard payload, product lookup, accounting liquid transfers, sales orders, Company print templates — do not invent parallel stacks.
6. Main `ci.yml` remains deploy-free (**Stage 18 C1**). Outline surface fidelity is honesty only — not every outline leaf as a new route Complete.

## Consequences

- Agents may implement Stage 96 plan items without reopening Stage 1–95 feature scope.
- Stage 96 exit requires `docs/STAGE_96_EXIT_CRITERIA.md` with no CRITICAL/MISSING rows for planned workstreams.
