# ADR-192: Stage 93 Delivery Track Opened

**Status:** Accepted  
**Date:** 2026-08-11  
**Supersedes (in part):** ADR-191 clause that blocked opening the next delivery track until explicit sign-off

## Context

Stage 92 House Console Workflow & Readiness Ops exit criteria are met (`docs/STAGE_92_EXIT_CRITERIA.md`) with B1–K1 / D1 / H92x Complete (ADR-191). Product owner approved opening Stage 93 after Stage 92 freeze via CONTINUE/NEXT with a distinct product outline:

```
Roster Navigation & Export
     ↓
Staff Delivery & Integrity
     ↓
Format, Evidence & Runtime Posture
     ↓
House Navigation & Runtime Ops
```

Audit after Stage 92 found:

| Area | Status |
|------|--------|
| Investigation export / evidence download / formats | EXISTS (Stage 92) |
| Industry catalog-driven filter / created_this_month / URL sync | MISSING / PARTIAL |
| Notes length limit / suspended_reason search / at-risk focus styling | MISSING / PARTIAL |
| PDF last-delivery / billing grace column | MISSING |
| Staff invite delivery persistence in users UI | PARTIAL |
| Audit verify timestamp formatting | MISSING |
| House number_format / idle timeout / Celery badge / CORS warning | MISSING / PARTIAL |
| Paid billing / membership / hard-delete / impersonation | DEFERRED / OUT |

## Decision

1. **Stage 93 delivery track is open** per `docs/STAGE_93_PLAN.md`.
2. **Stage 1–92 freezes remain** for their respective scopes.
3. Deliver Stage 93 **one workstream at a time** (M1 → J1 → V1 → D1 → H93x).
4. Explicitly out of this pass: paid billing / fabricated MRR / checkout / `subscriptions_live_claimed` Complete (ADR-002); User↔Store membership Complete (ADR-005); hard-delete Complete (ADR-003); impersonation; bulk suspend/activate; full notification center; reopening Stages 80–92 frozen scopes; main `ci.yml` deploy jobs. Honesty flags stay false: `mrr_fabricated_claimed: false`, `billing_complete_claimed: false`, `subscriptions_live_claimed: false`, `user_store_membership_claimed: false`, `hard_delete_claimed: false`, `sections_1_3_verified: false`, `section_7_signed: false`, `go_live_claimed: false`, `attestation_claimed: false`.
5. Extend proven tenant list/export, industry constants, invite delivery audits, settings/formats, and protected health/evidence — do not invent parallel stacks.
6. Main `ci.yml` remains deploy-free (**Stage 18 C1**). Evidence packaging remains honesty only — not §§1–3 / go-live Complete.

## Consequences

- Agents may implement Stage 93 plan items without reopening Stage 1–92 feature scope.
- Stage 93 exit requires `docs/STAGE_93_EXIT_CRITERIA.md` with no CRITICAL/MISSING rows for planned workstreams.
