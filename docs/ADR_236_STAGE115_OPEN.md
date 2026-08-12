# ADR-236: Stage 115 Delivery Track Opened

**Status:** Accepted  
**Date:** 2026-08-12  
**Supersedes (in part):** ADR-235 clause that blocked opening the next delivery track until explicit sign-off

## Context

Stage 114 Tenant MVP Residual Status & Ops Filter Discoverability exit criteria are met (`docs/STAGE_114_EXIT_CRITERIA.md`) with Q1–O1 / D1 / H114x Complete (ADR-235). Product owner approved opening Stage 115 after Stage 114 freeze via CONTINUE/NEXT with a distinct product outline — **Notification History Honesty & Residual Filter Discoverability** (Notification History `?status=all` honesty + Shell leaf, purchase invoice unpaid/partial/cancelled leaves, Draft Orders + Platform Users `role=` leaves), not another residual sales/PR/PO/transfer-scope pass:

```
Notification History Honesty
     ↓
Purchase Invoice Status Leaves
     ↓
Draft Orders & Platform Role Leaves
     ↓
Tenant MVP Notification History Honesty & Residual Filter Discoverability
```

Audit after Stage 114 found:

| Area | Status |
|------|--------|
| Residual sales/purchasing/ops filter leaves (114) | EXISTS (Stage 114 frozen) |
| Notification History deep-link | BROKEN / MISSING — empty status reloads as unread; Shell leaf MISSING |
| Purchase invoice unpaid/partial/cancelled Shell leaves | PARTIAL — page URL sync EXISTS; Shell leaves MISSING |
| Draft Orders Shell leaf | PARTIAL — page URL sync EXISTS; Shell leaf MISSING |
| Platform Users `?role=` leaves | PARTIAL — page URL sync EXISTS; PlatformShell leaves MISSING |
| POS Hold/Resume / ADR-002 / ADR-005 / hard-delete | DEFERRED / OUT |

## Decision

1. **Stage 115 delivery track is open** per `docs/STAGE_115_PLAN.md`.
2. **Stage 1–114 freezes remain** for their respective scopes (Stage 114 under ADR-235).
3. Deliver Stage 115 **one workstream at a time** (N1 → P1 → O1 → D1 → H115x).
4. Explicitly out of this pass: paid billing / fabricated MRR / checkout / `subscriptions_live_claimed` Complete (ADR-002); User↔Store membership Complete (ADR-005); hard-delete Complete (ADR-003); impersonation; POS Hold/Resume; full Billers CRUD; parallel Income; WYSIWYG; fiscal-period close; reopening Stages 80–114 frozen scopes; main `ci.yml` deploy jobs. Honesty flags stay false.
5. Extend proven Shell deep-links and existing URL query sync — do not invent parallel stacks. Fix Notification History deep-link honesty with a durable `status=all` sentinel.
6. Main `ci.yml` remains deploy-free (**Stage 18 C1**).

## Consequences

- Agents may implement Stage 115 plan items without reopening Stage 1–114 feature scope.
- Stage 115 exit requires `docs/STAGE_115_EXIT_CRITERIA.md` with no CRITICAL/MISSING rows for planned workstreams.
