# ADR-174: Stage 84 Delivery Track Opened

**Status:** Accepted  
**Date:** 2026-08-11  
**Supersedes (in part):** ADR-173 clause that blocked opening the next delivery track until explicit sign-off

## Context

Stage 83 Dual-Console Ops Fidelity exit criteria are met (`docs/STAGE_83_EXIT_CRITERIA.md`) with S1–U1 / D1 / H83x Complete (ADR-173). Product owner approved opening Stage 84 after Stage 83 freeze via CONTINUE/NEXT with a distinct product outline: **Dotted Permission Aliases → Tenant Dashboard Slice Depth → Dual-Console Permission & Slice Fidelity**.

Audit after Stage 83 found:

| Area | Status |
|------|--------|
| Canonical `module → [actions]` RBAC | EXISTS |
| Dotted / colon permission aliases (`inventory.view` ↔ `inventory:read`) | MISSING (deferred since Stage 80) |
| Expenses slice total | EXISTS |
| Expenses-by-category + credit outstanding slices | MISSING / PARTIAL |
| Cashier open-shift API | EXISTS (`GET /pos/sessions/current`) |
| Cashier open-shift on dashboard UI | MISSING |
| Paid billing / MRR | DEFERRED (ADR-002) |
| User↔Store membership | DEFERRED (ADR-005) |
| Admin email-initiated password reset | DEFERRED (Stage 85 candidate) |

Owner product outline:

```
Dual-Console Ops Packaged (Stage 83)
     ↓
Dotted Permission Aliases
     ↓
Tenant Dashboard Slice Depth (+ cashier polish)
     ↓
Dual-Console Permission & Slice Fidelity
```

## Decision

1. **Stage 84 delivery track is open** per `docs/STAGE_84_PLAN.md`.
2. **Stage 1–83 freezes remain** for their respective scopes.
3. Deliver Stage 84 **one workstream at a time** (A1 → S1 → D1 → H84x).
4. Explicitly out of this pass: paid billing / fabricated MRR (ADR-002); User↔Store membership Complete (ADR-005); admin email-initiated password reset; platform subscriptions roster as billing; reopening Stages 80–83 frozen scopes; main `ci.yml` deploy jobs. Honesty flags stay false for: `mrr_fabricated_claimed: false`, `billing_complete_claimed: false`, `user_store_membership_claimed: false`, `go_live_claimed: false`, `sections_1_3_verified: false`, `section_7_signed: false`.
5. Extend proven `rbac.normalize_permissions_map` / `has_permission` / `dashboard_slices` / `dashboard_views` patterns — do not invent parallel stacks.
6. Main `ci.yml` remains deploy-free (**Stage 18 C1**).

## Consequences

- Agents may implement Stage 84 plan items without reopening Stage 1–83 feature scope.
- Stage 84 exit requires `docs/STAGE_84_EXIT_CRITERIA.md` with no CRITICAL/MISSING rows for planned workstreams.
