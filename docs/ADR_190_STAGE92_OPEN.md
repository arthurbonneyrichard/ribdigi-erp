# ADR-190: Stage 92 Delivery Track Opened

**Status:** Accepted  
**Date:** 2026-08-11  
**Supersedes (in part):** ADR-189 clause that blocked opening the next delivery track until explicit sign-off

## Context

Stage 91 House Operator Investigation & Evidence Ops exit criteria are met (`docs/STAGE_91_EXIT_CRITERIA.md`) with I1–P1 / D1 / H91x Complete (ADR-189). Product owner approved opening Stage 92 after Stage 91 freeze via CONTINUE/NEXT with a distinct product outline:

```
Investigation Export & Evidence Download
     ↓
Roster Triage & Commercial-Metadata Context
     ↓
House Regional Formats & Runtime Evidence Detail
     ↓
House Console Workflow & Readiness Ops
```

Audit after Stage 91 found:

| Area | Status |
|------|--------|
| Audit list date-range + Activity 7d default | EXISTS (Stage 91) |
| Audit export `delivery_only` + Activity export window parity | MISSING / PARTIAL |
| Evidence download UI | MISSING |
| Dashboard Active/Trial deep-links | MISSING |
| Platform notes search / list last delivery projection | MISSING |
| Billing roster commercial-metadata columns | PARTIAL |
| Provision plan soft-limit context | MISSING |
| House date/time formats on settings | MISSING |
| Protected CORS allowlist on health/evidence | PARTIAL |
| Paid billing / membership / hard-delete / impersonation | DEFERRED / OUT |

## Decision

1. **Stage 92 delivery track is open** per `docs/STAGE_92_PLAN.md`.
2. **Stage 1–91 freezes remain** for their respective scopes.
3. Deliver Stage 92 **one workstream at a time** (B1 → G1 → K1 → D1 → H92x).
4. Explicitly out of this pass: paid billing / fabricated MRR / checkout / `subscriptions_live_claimed` Complete (ADR-002); User↔Store membership Complete (ADR-005); hard-delete Complete (ADR-003); impersonation; bulk suspend/activate; full notification center; reopening Stages 80–91 frozen scopes; main `ci.yml` deploy jobs. Honesty flags stay false: `mrr_fabricated_claimed: false`, `billing_complete_claimed: false`, `subscriptions_live_claimed: false`, `user_store_membership_claimed: false`, `hard_delete_claimed: false`, `sections_1_3_verified: false`, `section_7_signed: false`, `go_live_claimed: false`, `attestation_claimed: false`.
5. Extend proven audit export, tenant list/export, subscriptions roster, platform settings, and protected health/evidence — do not invent parallel stacks.
6. Main `ci.yml` remains deploy-free (**Stage 18 C1**). Evidence packaging remains honesty only — not §§1–3 / go-live Complete.

## Consequences

- Agents may implement Stage 92 plan items without reopening Stage 1–91 feature scope.
- Stage 92 exit requires `docs/STAGE_92_EXIT_CRITERIA.md` with no CRITICAL/MISSING rows for planned workstreams.
