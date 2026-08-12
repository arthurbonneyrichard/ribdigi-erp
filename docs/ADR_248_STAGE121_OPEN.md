# ADR-248: Stage 121 Delivery Track Opened

**Status:** Accepted  
**Date:** 2026-08-12  
**Supersedes (in part):** ADR-247 clause that blocked opening the next delivery track until explicit sign-off

## Context

Stage 120 Tenant MVP Inactive Products, Users CSV Export & Expenses CSV Export Fidelity exit criteria are met (`docs/STAGE_120_EXIT_CRITERIA.md`) with P1–X1 / D1 / H120x Complete (ADR-247). Product owner approved opening Stage 121 after Stage 120 freeze via CONTINUE/NEXT with a distinct **non-discoverability** product outline — **Inactive Stores & Warehouses & Location CSV Export Fidelity** (store/warehouse active-status list honesty parity with Stage 118–120 parties/products, and stores/warehouses/tax-rates CSV export), not PO OCR / Billers CRUD / POS Hold / percentage-discount polish:

```
Inactive Stores Honesty
     ↓
Inactive Warehouses Honesty
     ↓
Location CSV Export
     ↓
Tenant MVP Inactive Stores & Warehouses & Location CSV Export Fidelity
```

Audit after Stage 120 found:

| Area | Status |
|------|--------|
| Inactive customers / suppliers / products / party+user+expense export | EXISTS (Stages 118–120 frozen) |
| Inactive stores list honesty | PARTIAL — deactivate/`is_active` EXISTS; list filter MISSING |
| Inactive warehouses list honesty | PARTIAL — deactivate/`is_active` EXISTS; list filter MISSING |
| Stores / warehouses / tax rates CSV export | PARTIAL / MISSING |
| PO OCR / POS Hold/Resume / ADR-002 / ADR-005 / Billers CRUD / WYSIWYG | DEFERRED / OUT |

## Decision

1. **Stage 121 delivery track is open** per `docs/STAGE_121_PLAN.md`.
2. **Stage 1–120 freezes remain** for their respective scopes (Stage 120 under ADR-247).
3. Deliver Stage 121 **one workstream at a time** (S1 → W1 → X1 → D1 → H121x).
4. Explicitly out of this pass: paid billing / fabricated MRR / checkout / `subscriptions_live_claimed` Complete (ADR-002); User↔Store membership Complete (ADR-005); hard-delete Complete (ADR-003); impersonation; POS Hold/Resume; full Billers CRUD; parallel Income; WYSIWYG designer Complete; PO OCR apply; percentage discount UI polish; year-end tax wizard / multi-book; reopening Stages 80–120 frozen scopes; main `ci.yml` deploy jobs. Honesty flags stay false.
5. Extend proven party/product status filters and CSV export patterns — do not invent parallel stacks.
6. Main `ci.yml` remains deploy-free (**Stage 18 C1**).

## Consequences

- Agents may implement Stage 121 plan items without reopening Stage 1–120 feature scope.
- Stage 121 exit requires `docs/STAGE_121_EXIT_CRITERIA.md` with no CRITICAL/MISSING rows for planned workstreams.
