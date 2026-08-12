# ADR-194: Stage 94 Delivery Track Opened

**Status:** Accepted  
**Date:** 2026-08-11  
**Supersedes (in part):** ADR-193 clause that blocked opening the next delivery track until explicit sign-off

## Context

Stage 93 House Navigation & Runtime Ops exit criteria are met (`docs/STAGE_93_EXIT_CRITERIA.md`) with M1–V1 / D1 / H93x Complete (ADR-193). Product owner approved opening Stage 94 after Stage 93 freeze via CONTINUE/NEXT with a distinct product outline:

```
Platform Staff Discovery
     ↓
Configuration Integrity & Release Identity
     ↓
Console State & Queue Awareness
     ↓
House Discovery & Runtime Assurance Ops
```

Audit after Stage 93 found:

| Area | Status |
|------|--------|
| Roster navigation / formats / evidence packaging | EXISTS (Stage 93) |
| Platform users search / role / active filters | MISSING |
| Dashboard Platform-users deep-link | MISSING |
| Support email + timezone server validation | PARTIAL / MISSING |
| Protected runtime identity (version/build) | MISSING |
| Shell at-risk badge / Activity empty distinction / Plans chart link | MISSING / PARTIAL |
| Paid billing / membership / hard-delete / impersonation | DEFERRED / OUT |

## Decision

1. **Stage 94 delivery track is open** per `docs/STAGE_94_PLAN.md`.
2. **Stage 1–93 freezes remain** for their respective scopes.
3. Deliver Stage 94 **one workstream at a time** (W1 → H1 → T2 → D1 → H94x).
4. Explicitly out of this pass: paid billing / fabricated MRR / checkout / `subscriptions_live_claimed` Complete (ADR-002); User↔Store membership Complete (ADR-005); hard-delete Complete (ADR-003); impersonation; bulk suspend/activate; full notification center; reopening Stages 80–93 frozen scopes; main `ci.yml` deploy jobs. Honesty flags stay false: `mrr_fabricated_claimed: false`, `billing_complete_claimed: false`, `subscriptions_live_claimed: false`, `user_store_membership_claimed: false`, `hard_delete_claimed: false`, `sections_1_3_verified: false`, `section_7_signed: false`, `go_live_claimed: false`, `attestation_claimed: false`.
5. Extend proven platform users list, settings validation, health/evidence, PlatformShell — do not invent parallel stacks.
6. Main `ci.yml` remains deploy-free (**Stage 18 C1**). Runtime identity packaging is honesty only — not §§1–3 / go-live Complete.

## Consequences

- Agents may implement Stage 94 plan items without reopening Stage 1–93 feature scope.
- Stage 94 exit requires `docs/STAGE_94_EXIT_CRITERIA.md` with no CRITICAL/MISSING rows for planned workstreams.
