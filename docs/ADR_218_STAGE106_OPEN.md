# ADR-218: Stage 106 Delivery Track Opened

**Status:** Accepted  
**Date:** 2026-08-12  
**Supersedes (in part):** ADR-217 clause that blocked opening the next delivery track until explicit sign-off

## Context

Stage 105 Tenant MVP Permissions Matrix, Store Policies & Platform Audit Ops exit criteria are met (`docs/STAGE_105_EXIT_CRITERIA.md`) with P1–A1 / D1 / H105x Complete (ADR-217). Product owner approved opening Stage 106 after Stage 105 freeze via CONTINUE/NEXT with a distinct product outline — **Approval Filters, Company Profile & Notification Inbox Ops** (expense scope URL filters, purchase-settings hash, company profile/logo/locale/departments, notification inbox leaves), not another permissions/FEFO/platform-audit pass:

```
Expense Scope & Purchase Settings Honesty
     ↓
Company Profile & Departments Discoverability
     ↓
Notification Inbox Leaves
     ↓
Tenant MVP Approval Filters, Company Profile & Notification Inbox Ops
```

Audit after Stage 105 found:

| Area | Status |
|------|--------|
| Permissions / FEFO-reorder / platform audit URL | EXISTS (Stage 105 frozen) |
| Expense `store_id`/`department_id` shareable filters | PARTIAL — API+UI exist; only `status` URL-synced |
| Purchase Settings `#purchase-settings` Shell scroll | PARTIAL — id exists; Shell leaf bare `?tab=settings` |
| Company logo/profile/locale/departments Shell | MISSING (branches/numbering/media frozen Stage 103) |
| Notification unread/group Shell leaves | MISSING — URL sync already works (Stage 101) |
| POS Hold/Resume / ADR-002 / ADR-005 / hard-delete | DEFERRED / OUT |

## Decision

1. **Stage 106 delivery track is open** per `docs/STAGE_106_PLAN.md`.
2. **Stage 1–105 freezes remain** for their respective scopes (Stage 105 under ADR-217).
3. Deliver Stage 106 **one workstream at a time** (E1 → C1 → N1 → D1 → H106x).
4. Explicitly out of this pass: paid billing / fabricated MRR / checkout / `subscriptions_live_claimed` Complete (ADR-002); User↔Store membership Complete (ADR-005); hard-delete Complete (ADR-003); impersonation; POS Hold/Resume; full Billers CRUD; parallel Income; WYSIWYG; fiscal-period close; reopening Stages 80–105 frozen scopes; main `ci.yml` deploy jobs. Honesty flags stay false.
5. Extend proven Shell deep-links, URL query sync, and page hash scroll — do not invent parallel stacks.
6. Main `ci.yml` remains deploy-free (**Stage 18 C1**).

## Consequences

- Agents may implement Stage 106 plan items without reopening Stage 1–105 feature scope.
- Stage 106 exit requires `docs/STAGE_106_EXIT_CRITERIA.md` with no CRITICAL/MISSING rows for planned workstreams.
