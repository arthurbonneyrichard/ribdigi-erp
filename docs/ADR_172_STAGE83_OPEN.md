# ADR-172: Stage 83 Delivery Track Opened

**Status:** Accepted  
**Date:** 2026-08-11  
**Supersedes (in part):** ADR-171 clause that blocked opening the next delivery track until explicit sign-off

## Context

Stage 82 Dual-Console Surface Parity exit criteria are met (`docs/STAGE_82_EXIT_CRITERIA.md`) with C1–D1 / H82x Complete (ADR-171). Product owner approved opening Stage 83 after Stage 82 freeze via CONTINUE/NEXT with a distinct product outline: **Store-Scoped Chart Depth → Tenant Admin User Ops → Dual-Console Ops Fidelity**.

Audit after Stage 82 found:

| Area | Status |
|------|--------|
| Store Manager KPI totals | EXISTS (Stage 81 `scoped_financial_kpis`) |
| Store Manager chart/slice series | MISSING (tenant-wide leakage) |
| Admin password reset API | EXISTS (`PATCH /users/{id}` password) |
| Admin password reset + org edit UI | MISSING / PARTIAL |
| Paid billing / MRR | DEFERRED (ADR-002) |
| User↔Store membership | DEFERRED (ADR-005) |

Owner product outline:

```
Dual-Console Surface Packaged (Stage 82)
     ↓
Store-Scoped Chart Depth
     ↓
Tenant Admin User Ops
     ↓
Dual-Console Ops Fidelity
```

## Decision

1. **Stage 83 delivery track is open** per `docs/STAGE_83_PLAN.md`.
2. **Stage 1–82 freezes remain** for their respective scopes.
3. Deliver Stage 83 **one workstream at a time** (S1 → U1 → D1 → H83x).
4. Explicitly out of this pass: paid billing / fabricated MRR (ADR-002); User↔Store membership Complete (ADR-005); dotted permission aliases; reopening Stages 80–82 frozen scopes; main `ci.yml` deploy jobs. Honesty flags stay false for: `mrr_fabricated_claimed: false`, `billing_complete_claimed: false`, `user_store_membership_claimed: false`, `go_live_claimed: false`, `sections_1_3_verified: false`, `section_7_signed: false`.
5. Extend proven `dashboard_scope` / `dashboard_charts` / `PATCH /users` patterns — do not invent parallel stacks.
6. Main `ci.yml` remains deploy-free (**Stage 18 C1**).

## Consequences

- Agents may implement Stage 83 plan items without reopening Stage 1–82 feature scope.
- Stage 83 exit requires `docs/STAGE_83_EXIT_CRITERIA.md` with no CRITICAL/MISSING rows for planned workstreams.
