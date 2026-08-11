# ADR-170: Stage 82 Delivery Track Opened

**Status:** Accepted  
**Date:** 2026-08-11  
**Supersedes (in part):** ADR-169 clause that blocked opening the next delivery track until explicit sign-off

## Context

Stage 81 Dual-Console Admin Fidelity exit criteria are met (`docs/STAGE_81_EXIT_CRITERIA.md`) with A1–D1 / H81x Complete (ADR-169). Product owner approved opening Stage 82 after Stage 81 freeze via CONTINUE/NEXT with a distinct product outline: **Tenant Dashboard Chart Subroutes → Platform Plans Console → Dual-Console Surface Parity**.

Audit after Stage 81 found:

| Area | Status |
|------|--------|
| Tenant `/dashboard` monolith | EXISTS |
| Tenant chart/KPI subroutes | MISSING |
| Platform plan_code PATCH | EXISTS |
| Platform Plans nav/page | MISSING |
| Admin Activity alias | MISSING (`/audit` only) |
| Paid billing / MRR | DEFERRED (ADR-002) |
| User↔Store membership | DEFERRED (ADR-005) |

Owner product outline:

```
Dual-Console Admin Packaged (Stage 81)
     ↓
Tenant Dashboard Chart Subroutes
     ↓
Platform Plans Console
     ↓
Dual-Console Surface Parity
```

## Decision

1. **Stage 82 delivery track is open** per `docs/STAGE_82_PLAN.md`.
2. **Stage 1–81 freezes remain** for their respective scopes.
3. Deliver Stage 82 **one workstream at a time** (C1 → P1 → D1 → H82x).
4. Explicitly out of this pass: paid billing / fabricated MRR (ADR-002); User↔Store membership Complete (ADR-005); reopening Stage 80 platform chart packs; reopening Stage 81 A1/S1; inventing fake plan revenue; main `ci.yml` deploy jobs. Honesty flags stay false for: `mrr_fabricated_claimed: false`, `billing_complete_claimed: false`, `user_store_membership_claimed: false`, `go_live_claimed: false`, `sections_1_3_verified: false`, `section_7_signed: false`.
5. Extend proven `/dashboard` + `/platform/dashboard/*` + plan_code metadata patterns — do not invent parallel billing.
6. Main `ci.yml` remains deploy-free (**Stage 18 C1**).

## Consequences

- Agents may implement Stage 82 plan items without reopening Stage 1–81 feature scope.
- Stage 82 exit requires `docs/STAGE_82_EXIT_CRITERIA.md` with no CRITICAL/MISSING rows for planned workstreams.
