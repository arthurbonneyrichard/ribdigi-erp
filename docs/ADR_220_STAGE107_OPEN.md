# ADR-220: Stage 107 Delivery Track Opened

**Status:** Accepted  
**Date:** 2026-08-12  
**Supersedes (in part):** ADR-219 clause that blocked opening the next delivery track until explicit sign-off

## Context

Stage 106 Tenant MVP Approval Filters, Company Profile & Notification Inbox Ops exit criteria are met (`docs/STAGE_106_EXIT_CRITERIA.md`) with E1–N1 / D1 / H106x Complete (ADR-219). Product owner approved opening Stage 107 after Stage 106 freeze via CONTINUE/NEXT with a distinct product outline — **POS Sections, Commerce Filters & Ops Leaves Ops** (POS shift/cart/receipt hash sections, sales `active_only` + inventory product list URL filters, platform at-risk/new tenants + backup history leaves), not another expense/company/notification pass:

```
POS Sections Honesty
     ↓
Commerce Filters Honesty
     ↓
Ops Leaves Discoverability
     ↓
Tenant MVP POS Sections, Commerce Filters & Ops Leaves Ops
```

Audit after Stage 106 found:

| Area | Status |
|------|--------|
| Expense / company profile / notification inbox | EXISTS (Stage 106 frozen) |
| POS `#sessions` Shell scroll | EXISTS (Stage 101); `#shift` / `#cart` / `#receipt` | PARTIAL / MISSING |
| Sales customers/groups `active_only` shareable URL | PARTIAL — API exists; page/Shell incomplete |
| Inventory product list `q` / `category_id` / `brand_id` URL | MISSING (client-side OK; GET /products has no server filters) |
| Platform At-risk / New Tenants Shell leaves | PARTIAL — page URL sync exists; PlatformShell leaves MISSING |
| Backup `#history` Shell leaf | MISSING (schedule/restore frozen Stage 103) |
| POS Hold/Resume / ADR-002 / ADR-005 / hard-delete | DEFERRED / OUT |

## Decision

1. **Stage 107 delivery track is open** per `docs/STAGE_107_PLAN.md`.
2. **Stage 1–106 freezes remain** for their respective scopes (Stage 106 under ADR-219).
3. Deliver Stage 107 **one workstream at a time** (P1 → S1 → O1 → D1 → H107x).
4. Explicitly out of this pass: paid billing / fabricated MRR / checkout / `subscriptions_live_claimed` Complete (ADR-002); User↔Store membership Complete (ADR-005); hard-delete Complete (ADR-003); impersonation; POS Hold/Resume; full Billers CRUD; parallel Income; WYSIWYG; fiscal-period close; reopening Stages 80–106 frozen scopes; main `ci.yml` deploy jobs. Honesty flags stay false.
5. Extend proven Shell deep-links, URL query sync, and page hash scroll — do not invent parallel stacks.
6. Main `ci.yml` remains deploy-free (**Stage 18 C1**).

## Consequences

- Agents may implement Stage 107 plan items without reopening Stage 1–106 feature scope.
- Stage 107 exit requires `docs/STAGE_107_EXIT_CRITERIA.md` with no CRITICAL/MISSING rows for planned workstreams.
