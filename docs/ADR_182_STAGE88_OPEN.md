# ADR-182: Stage 88 Delivery Track Opened

**Status:** Accepted  
**Date:** 2026-08-11  
**Supersedes (in part):** ADR-181 clause that blocked opening the next delivery track until explicit sign-off

## Context

Stage 87 House Integrity & Console Boundary Ops exit criteria are met (`docs/STAGE_87_EXIT_CRITERIA.md`) with X1–Z1 / D1 / H87x Complete (ADR-181). Product owner approved opening Stage 88 after Stage 87 freeze via CONTINUE/NEXT with a distinct product outline:

```
Tenant Lifecycle Controls
     ↓
Tenant Roster Export & At-Risk Queue
     ↓
Platform Staff Invite & Session Ops
     ↓
House Lifecycle & Staff Security Ops
```

Audit after Stage 87 found:

| Area | Status |
|------|--------|
| Platform audit export / verify | EXISTS (Stage 87 X1) |
| Trial/grace fields on serialize | EXISTS API / MISSING House lifecycle controls UI |
| Suspend reason from House | PARTIAL (hardcoded reason) |
| Tenant roster export / at-risk queue | MISSING |
| Platform staff invite without temp password | MISSING |
| Platform staff session browser | MISSING (self `/auth/sessions` only) |
| Paid billing / membership / hard-delete | DEFERRED |

## Decision

1. **Stage 88 delivery track is open** per `docs/STAGE_88_PLAN.md`.
2. **Stage 1–87 freezes remain** for their respective scopes.
3. Deliver Stage 88 **one workstream at a time** (L1 → R1 → S1 → D1 → H88x).
4. Explicitly out of this pass: paid billing / fabricated MRR / checkout / `subscriptions_live_claimed` Complete (ADR-002); User↔Store membership Complete (ADR-005); hard-delete Complete (ADR-003); reopening Stages 80–87 frozen scopes; main `ci.yml` deploy jobs. Honesty flags stay false: `mrr_fabricated_claimed: false`, `billing_complete_claimed: false`, `subscriptions_live_claimed: false`, `user_store_membership_claimed: false`, `hard_delete_claimed: false`, `sections_1_3_verified: false`, `section_7_signed: false`, `go_live_claimed: false`, `attestation_claimed: false`.
5. Extend proven trial/grace, suspend/activate, audit export, and one-time email token / AuthSession revoke patterns — do not invent parallel stacks.
6. Main `ci.yml` remains deploy-free (**Stage 18 C1**). Activate/extend-trial remain metadata lifecycle ops — not paid billing Complete.

## Consequences

- Agents may implement Stage 88 plan items without reopening Stage 1–87 feature scope.
- Stage 88 exit requires `docs/STAGE_88_EXIT_CRITERIA.md` with no CRITICAL/MISSING rows for planned workstreams.

## Closeout

Stage 88 exit met — see [STAGE_88_EXIT_CRITERIA.md](STAGE_88_EXIT_CRITERIA.md) and freeze [ADR-183](ADR_183_STAGE88_FREEZE.md).
