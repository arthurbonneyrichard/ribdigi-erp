# ADR-214: Stage 104 Delivery Track Opened

**Status:** Accepted  
**Date:** 2026-08-12  
**Supersedes (in part):** ADR-213 clause that blocked opening the next delivery track until explicit sign-off

## Context

Stage 103 Tenant MVP Security, Backup & Company Org Ops exit criteria are met (`docs/STAGE_103_EXIT_CRITERIA.md`) with S1–C1 / D1 / H103x Complete (ADR-213). Product owner approved opening Stage 104 after Stage 103 freeze via CONTINUE/NEXT with a distinct product outline — **Ledger Filters, Commerce Leaves & Admin Ops** (journal/cheque URL filters, commerce Shell leaves, credit/roles discoverability), not another security/backup/company-org pass:

```
Ledger Journal & Cheque Filter Honesty
     ↓
Commerce Products / Purchase Invoices / Sales Status Leaves
     ↓
Credit Section & Admin Roles Discoverability
     ↓
Tenant MVP Ledger Filters, Commerce Leaves & Admin Ops
```

Audit after Stage 103 found:

| Area | Status |
|------|--------|
| Security / Backup / Company org Shell honesty | EXISTS (Stage 103 frozen) |
| Journal `status` / store URL sync; Cheques UI direction/status filters | PARTIAL / MISSING — API exists, URL/UI incomplete |
| Shell Products; bare Purchase Invoices; Draft/Overdue sales invoices | MISSING leaves (UI/URL sync exists) |
| Credit section anchors; Roles `#custom`/`#system`; Custom Roles KPI → `/admin/roles` | MISSING / PARTIAL |
| POS Hold/Resume / ADR-002 / ADR-005 / hard-delete | DEFERRED / OUT |

## Decision

1. **Stage 104 delivery track is open** per `docs/STAGE_104_PLAN.md`.
2. **Stage 1–103 freezes remain** for their respective scopes (Stage 103 under ADR-213).
3. Deliver Stage 104 **one workstream at a time** (A1 → I1 → R1 → D1 → H104x).
4. Explicitly out of this pass: paid billing / fabricated MRR / checkout / `subscriptions_live_claimed` Complete (ADR-002); User↔Store membership Complete (ADR-005); hard-delete Complete (ADR-003); impersonation; POS Hold/Resume; full Billers CRUD; parallel Income; WYSIWYG; fiscal-period close; reopening Stages 80–103 frozen scopes; main `ci.yml` deploy jobs. Honesty flags stay false.
5. Extend proven Shell deep-links, URL query sync, and page hash scroll — do not invent parallel stacks.
6. Main `ci.yml` remains deploy-free (**Stage 18 C1**).

## Consequences

- Agents may implement Stage 104 plan items without reopening Stage 1–103 feature scope.
- Stage 104 exit requires `docs/STAGE_104_EXIT_CRITERIA.md` with no CRITICAL/MISSING rows for planned workstreams.
