# ADR-168: Stage 81 Delivery Track Opened

**Status:** Accepted  
**Date:** 2026-08-11  
**Supersedes (in part):** ADR-167 clause that blocked opening the next delivery track until explicit sign-off

## Context

Stage 80 Dual-Console Dashboard Fidelity exit criteria are met (`docs/STAGE_80_EXIT_CRITERIA.md`) with P1–D1 / H80x Complete (ADR-167). Product owner approved opening Stage 81 after Stage 80 freeze via CONTINUE/NEXT with a distinct product outline: **Tenant Admin RBAC Console Surfaces → Store-Scoped Manager Ops → Dual-Console Admin Fidelity**.

Audit after Stage 80 found:

| Area | Status |
|------|--------|
| Platform charts + role view labels | EXISTS (Stage 80; frozen) |
| Tenant Admin Users page (combined) | EXISTS (`/users`) |
| Admin nav Roles / Permissions split | MISSING |
| Store Manager aggregate store scoping (`stores.manager_id`) | MISSING (view label only) |
| User PATCH/DELETE cross-tenant isolation tests | MISSING (GET exists) |
| Paid billing / MRR | DEFERRED (ADR-002) |
| User↔Store membership table | DEFERRED (ADR-005) |

Owner product outline:

```
Dual-Console Dashboard Packaged (Stage 80)
     ↓
Tenant Admin RBAC Console Surfaces
     ↓
Store-Scoped Manager Ops
     ↓
Dual-Console Admin Fidelity
```

## Decision

1. **Stage 81 delivery track is open** per `docs/STAGE_81_PLAN.md`.
2. **Stage 1–80 freezes remain** for their respective scopes.
3. Deliver Stage 81 **one workstream at a time** (A1 → S1 → D1 → H81x).
4. Explicitly out of this pass: paid billing / fabricated MRR (ADR-002); User↔Store membership table Complete (ADR-005); reopening Stage 80 chart packs; inventing fake store metrics; reopening Stages 1–80 frozen feature scopes; main `ci.yml` deploy jobs. Honesty flags stay false for: `mrr_fabricated_claimed: false`, `billing_complete_claimed: false`, `user_store_membership_claimed: false`, `go_live_claimed: false`, `sections_1_3_verified: false`, `section_7_signed: false`.
5. Extend proven `/users` + `stores.manager_id` + ADR-137 patterns — do not invent a parallel RBAC stack.
6. Main `ci.yml` remains deploy-free (**Stage 18 C1**).

## Consequences

- Agents may implement Stage 81 plan items without reopening Stage 1–80 feature scope.
- Stage 81 exit requires `docs/STAGE_81_EXIT_CRITERIA.md` with no CRITICAL/MISSING rows for planned workstreams.
