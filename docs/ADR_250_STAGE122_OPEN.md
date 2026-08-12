# ADR-250: Stage 122 Delivery Track Opened

**Status:** Accepted  
**Date:** 2026-08-12  
**Supersedes (in part):** ADR-249 clause that blocked opening the next delivery track until explicit sign-off

## Context

Stage 121 Tenant MVP Inactive Stores & Warehouses & Location CSV Export Fidelity exit criteria are met (`docs/STAGE_121_EXIT_CRITERIA.md`) with S1–W1 / X1 / D1 / H121x Complete (ADR-249). Product owner approved opening Stage 122 after Stage 121 freeze via CONTINUE/NEXT with a distinct **non-discoverability** product outline — **Inactive Org Units & Catalog Meta Honesty & Org/Catalog-Meta CSV Export Fidelity** (branch/department and category/brand/unit active-status list honesty parity with Stage 118–121, plus CSV export for those master-data families), not PO OCR / Billers CRUD / POS Hold / percentage-discount polish:

```
Inactive Org Units Honesty
     ↓
Inactive Catalog Meta Honesty
     ↓
Org & Catalog-Meta CSV Export
     ↓
Tenant MVP Inactive Org Units, Catalog Meta & Org/Catalog-Meta CSV Export Fidelity
```

Audit after Stage 121 found:

| Area | Status |
|------|--------|
| Inactive parties / products / stores / warehouses | EXISTS (Stages 118–121 frozen) |
| Inactive branches / departments list honesty | PARTIAL — deactivate/`is_active` EXISTS; inactive-only list filter MISSING |
| Inactive categories / brands / units list honesty | PARTIAL — deactivate/`is_active` EXISTS; list filter MISSING |
| Branches / departments / catalog-meta CSV export | MISSING |
| PO OCR / POS Hold/Resume / ADR-002 / ADR-005 / Billers CRUD / WYSIWYG | DEFERRED / OUT |

## Decision

1. **Stage 122 delivery track is open** per `docs/STAGE_122_PLAN.md`.
2. **Stage 1–121 freezes remain** for their respective scopes (Stage 121 under ADR-249).
3. Deliver Stage 122 **one workstream at a time** (O1 → M1 → X1 → D1 → H122x).
4. Explicitly out of this pass: paid billing / fabricated MRR / checkout / `subscriptions_live_claimed` Complete (ADR-002); User↔Store membership Complete (ADR-005); hard-delete Complete (ADR-003); impersonation; POS Hold/Resume; full Billers CRUD; parallel Income; WYSIWYG designer Complete; PO OCR apply; percentage discount UI polish; year-end tax wizard / multi-book; reopening Stages 80–121 frozen scopes; main `ci.yml` deploy jobs. Honesty flags stay false.
5. Extend proven party/product/location status filters and CSV export patterns — do not invent parallel stacks.
6. Main `ci.yml` remains deploy-free (**Stage 18 C1**).

## Consequences

- Agents may implement Stage 122 plan items without reopening Stage 1–121 feature scope.
- Stage 122 exit requires `docs/STAGE_122_EXIT_CRITERIA.md` with no CRITICAL/MISSING rows for planned workstreams.
