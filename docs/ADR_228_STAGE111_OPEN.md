# ADR-228: Stage 111 Delivery Track Opened

**Status:** Accepted  
**Date:** 2026-08-12  
**Supersedes (in part):** ADR-227 clause that blocked opening the next delivery track until explicit sign-off

## Context

Stage 110 Tenant MVP Purchasing Status Leaves, Expense Decision Queue & Admin Audit Ops exit criteria are met (`docs/STAGE_110_EXIT_CRITERIA.md`) with P1–A1 / D1 / H110x Complete (ADR-227). Product owner approved opening Stage 111 after Stage 110 freeze via CONTINUE/NEXT with a distinct product outline — **Inventory Movement Type Leaves, Posted Sales Returns & Cheque Hash Ops** (inventory `movement_type` Shell leaves + warehouse URL sync, Posted Sales Returns leaf, accounting `#cheques` hash polish + deposited/cleared leaves), not another purchasing/expense/admin-audit pass:

```
Inventory Movement Type Shell Leaves
     ↓
Posted Sales Returns Shell Leaf
     ↓
Accounting Cheque Hash & Residual Status Leaves
     ↓
Tenant MVP Inventory Movement Type Leaves, Posted Sales Returns & Cheque Hash Ops
```

Audit after Stage 110 found:

| Area | Status |
|------|--------|
| Purchasing status / expense queue / Create Role / Audit modules | EXISTS (Stage 110 frozen) |
| Inventory `movement_type` Shell leaves | MISSING — page URL sync EXISTS; Shell bare Movements only |
| Movements `warehouse_id` URL | PARTIAL — UI filter exists; not shareable |
| Posted Sales Returns Shell | MISSING (Stage 109 draft-only) |
| Accounting `#cheques` hash | PARTIAL — id exists; Shell leaves bare `?tab=cheques`; hash does not switch tab |
| Deposited / Cleared cheque Shell leaves | MISSING — page filters exist; Shell pending-only |
| POS Hold/Resume / ADR-002 / ADR-005 / hard-delete | DEFERRED / OUT |

## Decision

1. **Stage 111 delivery track is open** per `docs/STAGE_111_PLAN.md`.
2. **Stage 1–110 freezes remain** for their respective scopes (Stage 110 under ADR-227).
3. Deliver Stage 111 **one workstream at a time** (I1 → S1 → C1 → D1 → H111x).
4. Explicitly out of this pass: paid billing / fabricated MRR / checkout / `subscriptions_live_claimed` Complete (ADR-002); User↔Store membership Complete (ADR-005); hard-delete Complete (ADR-003); impersonation; POS Hold/Resume; full Billers CRUD; parallel Income; WYSIWYG; fiscal-period close; reopening Stages 80–110 frozen scopes; main `ci.yml` deploy jobs. Honesty flags stay false.
5. Extend proven Shell deep-links, URL query sync, and page hash scroll — do not invent parallel stacks.
6. Main `ci.yml` remains deploy-free (**Stage 18 C1**).

## Consequences

- Agents may implement Stage 111 plan items without reopening Stage 1–110 feature scope.
- Stage 111 exit requires `docs/STAGE_111_EXIT_CRITERIA.md` with no CRITICAL/MISSING rows for planned workstreams.
