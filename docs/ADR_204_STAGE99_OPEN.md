# ADR-204: Stage 99 Delivery Track Opened

**Status:** Accepted  
**Date:** 2026-08-12  
**Supersedes (in part):** ADR-203 clause that blocked opening the next delivery track until explicit sign-off

## Context

Stage 98 Tenant MVP Ops Queue & Returns Honesty Ops exit criteria are met (`docs/STAGE_98_EXIT_CRITERIA.md`) with Q1–O1 / D1 / H98x Complete (ADR-203). Product owner approved opening Stage 99 after Stage 98 freeze via CONTINUE/NEXT with a distinct product outline — remaining **document pipeline honesty** (Quote→Order, PR→PO→GRN, inventory lifecycle leaves), not another expense/returns/bank-recon pass:

```
Quote-to-Order Pipeline Honesty
     ↓
Purchase Request-to-GRN Pipeline Discoverability
     ↓
Inventory Lifecycle Leaf Discoverability
     ↓
Tenant MVP Document Pipeline Honesty Ops
```

Audit after Stage 98 found:

| Area | Status |
|------|--------|
| Invoice status / Pending Expenses / Returns / Stock Counts·Transfers / Bank Recon·Cheques / Credit kind | EXISTS (Stages 97–98 frozen) |
| Quotations Shell + status filter + quotation→order honesty | MISSING / PARTIAL |
| PR / PO / GRN Shell + status filters; purchase_order notification → invoices (wrong) | MISSING / PARTIAL |
| Variants / Batches / Expiry / Stock Adjustments / Catalog Brands·Units anchors | MISSING / PARTIAL |
| POS Hold/Resume / ADR-002 / ADR-005 / hard-delete / House reopen | DEFERRED / OUT |

## Decision

1. **Stage 99 delivery track is open** per `docs/STAGE_99_PLAN.md`.
2. **Stage 1–98 freezes remain** for their respective scopes (Stage 98 under ADR-203).
3. Deliver Stage 99 **one workstream at a time** (T1 → C1 → L1 → D1 → H99x).
4. Explicitly out of this pass: paid billing / fabricated MRR / checkout / `subscriptions_live_claimed` Complete (ADR-002); User↔Store membership Complete (ADR-005); hard-delete Complete (ADR-003); impersonation; full Billers CRUD; parallel Income module; WYSIWYG designer; fiscal-period close console; POS Hold/Resume; reopening Stages 80–98 frozen scopes; main `ci.yml` deploy jobs. Honesty flags stay false.
5. Extend proven sales quotations/orders, purchasing requests/orders/GRN, inventory catalog tabs + Shell deep-links — do not invent parallel stacks.
6. Main `ci.yml` remains deploy-free (**Stage 18 C1**).

## Consequences

- Agents may implement Stage 99 plan items without reopening Stage 1–98 feature scope.
- Stage 99 exit requires `docs/STAGE_99_EXIT_CRITERIA.md` with no CRITICAL/MISSING rows for planned workstreams.
