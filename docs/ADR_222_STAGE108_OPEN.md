# ADR-222: Stage 108 Delivery Track Opened

**Status:** Accepted  
**Date:** 2026-08-12  
**Supersedes (in part):** ADR-221 clause that blocked opening the next delivery track until explicit sign-off

## Context

Stage 107 Tenant MVP POS Sections, Commerce Filters & Ops Leaves Ops exit criteria are met (`docs/STAGE_107_EXIT_CRITERIA.md`) with P1–O1 / D1 / H107x Complete (ADR-221). Product owner approved opening Stage 108 after Stage 107 freeze via CONTINUE/NEXT with a distinct product outline — **AI Analysis Leaves, Credit Statement & Users Directory Ops** (AI analysis Shell leaves for orphan anchors, credit statement/party Shell leaves, tenant + platform users Active/Inactive directory leaves), not another POS/commerce-filters/ops-leaves pass:

```
AI Analysis Leaves Honesty
     ↓
Credit Statement Surfaces Discoverability
     ↓
Users Directory Leaves Discoverability
     ↓
Tenant MVP AI Analysis Leaves, Credit Statement & Users Directory Ops
```

Audit after Stage 107 found:

| Area | Status |
|------|--------|
| POS sections / commerce filters / backup history / platform at-risk | EXISTS (Stage 107 frozen) |
| AI analysis section anchors (`#sales-analysis` … `#low-stock`) | PARTIAL — anchors + scroll exist; Shell leaves MISSING (Stage 102 covered chat/forecast/dead-stock/insights/security only) |
| Credit `#party-actions` / `#by-party` / `#statement` | PARTIAL — anchors + scroll exist; Shell leaves MISSING (Stage 104 covered aging/early-pay/FX/schedule) |
| Users / Platform users `is_active` URL sync | PARTIAL — page URL sync EXISTS; Shell / PlatformShell Active/Inactive leaves MISSING |
| POS Hold/Resume / ADR-002 / ADR-005 / hard-delete | DEFERRED / OUT |

## Decision

1. **Stage 108 delivery track is open** per `docs/STAGE_108_PLAN.md`.
2. **Stage 1–107 freezes remain** for their respective scopes (Stage 107 under ADR-221).
3. Deliver Stage 108 **one workstream at a time** (A1 → C1 → U1 → D1 → H108x).
4. Explicitly out of this pass: paid billing / fabricated MRR / checkout / `subscriptions_live_claimed` Complete (ADR-002); User↔Store membership Complete (ADR-005); hard-delete Complete (ADR-003); impersonation; POS Hold/Resume; full Billers CRUD; parallel Income; WYSIWYG; fiscal-period close; reopening Stages 80–107 frozen scopes; main `ci.yml` deploy jobs. Honesty flags stay false.
5. Extend proven Shell deep-links, URL query sync, and page hash scroll — do not invent parallel stacks.
6. Main `ci.yml` remains deploy-free (**Stage 18 C1**).

## Consequences

- Agents may implement Stage 108 plan items without reopening Stage 1–107 feature scope.
- Stage 108 exit requires `docs/STAGE_108_EXIT_CRITERIA.md` with no CRITICAL/MISSING rows for planned workstreams.
