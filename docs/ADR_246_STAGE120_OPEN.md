# ADR-246: Stage 120 Delivery Track Opened

**Status:** Accepted  
**Date:** 2026-08-12  
**Supersedes (in part):** ADR-245 clause that blocked opening the next delivery track until explicit sign-off

## Context

Stage 119 Tenant MVP Inactive Suppliers, Party CSV Export & Print Template Preview Fidelity exit criteria are met (`docs/STAGE_119_EXIT_CRITERIA.md`) with S1–T1 / D1 / H119x Complete (ADR-245). Product owner approved opening Stage 120 after Stage 119 freeze via CONTINUE/NEXT with a distinct **non-discoverability** product outline — **Inactive Products, Users CSV Export & Expenses CSV Export Fidelity** (product active/inactive list honesty parity with Stage 118–119 parties, users CSV export aligned with import template, expenses CSV export), not another Shell filter-discoverability pack and not PO OCR / Billers CRUD / POS Hold:

```
Inactive Products Honesty
     ↓
Users CSV Export
     ↓
Expenses CSV Export
     ↓
Tenant MVP Inactive Products, Users CSV Export & Expenses CSV Export Fidelity
```

Audit after Stage 119 found:

| Area | Status |
|------|--------|
| Inactive customers / suppliers / party export / print preview | EXISTS (Stages 118–119 frozen) |
| Inactive products list honesty | PARTIAL — deactivate/`is_active` EXISTS; list `active_only` / inactive-only MISSING |
| Users CSV export | PARTIAL — import + template Complete; dedicated export MISSING |
| Expenses CSV export | PARTIAL / MISSING — list/status filters Complete; dedicated export MISSING |
| PO OCR / POS Hold/Resume / ADR-002 / ADR-005 / Billers CRUD / WYSIWYG | DEFERRED / OUT |

## Decision

1. **Stage 120 delivery track is open** per `docs/STAGE_120_PLAN.md`.
2. **Stage 1–119 freezes remain** for their respective scopes (Stage 119 under ADR-245).
3. Deliver Stage 120 **one workstream at a time** (P1 → U1 → X1 → D1 → H120x).
4. Explicitly out of this pass: paid billing / fabricated MRR / checkout / `subscriptions_live_claimed` Complete (ADR-002); User↔Store membership Complete (ADR-005); hard-delete Complete (ADR-003); impersonation; POS Hold/Resume; full Billers CRUD; parallel Income; WYSIWYG designer Complete; PO OCR apply; year-end tax wizard / multi-book; reopening Stages 80–119 frozen scopes; main `ci.yml` deploy jobs. Honesty flags stay false.
5. Extend proven party status filters, product/user import template columns, and expense list serialization — do not invent parallel stacks.
6. Main `ci.yml` remains deploy-free (**Stage 18 C1**).

## Consequences

- Agents may implement Stage 120 plan items without reopening Stage 1–119 feature scope.
- Stage 120 exit requires `docs/STAGE_120_EXIT_CRITERIA.md` with no CRITICAL/MISSING rows for planned workstreams.
