# ADR-216: Stage 105 Delivery Track Opened

**Status:** Accepted  
**Date:** 2026-08-12  
**Supersedes (in part):** ADR-215 clause that blocked opening the next delivery track until explicit sign-off

## Context

Stage 104 Tenant MVP Ledger Filters, Commerce Leaves & Admin Ops exit criteria are met (`docs/STAGE_104_EXIT_CRITERIA.md`) with A1–R1 / D1 / H104x Complete (ADR-215). Product owner approved opening Stage 105 after Stage 104 freeze via CONTINUE/NEXT with a distinct product outline — **Permissions Matrix, Store Policies & Platform Audit Ops** (permissions URL/hash honesty, store FEFO/reorder leaves, platform audit shareable filters), not another ledger/commerce/credit-roles pass:

```
Permissions Matrix Honesty
     ↓
Store Policy Leaves (FEFO / Reorder)
     ↓
Platform Audit Filter URL Sync
     ↓
Tenant MVP Permissions Matrix, Store Policies & Platform Audit Ops
```

Audit after Stage 104 found:

| Area | Status |
|------|--------|
| Journal/cheque filters; commerce leaves; credit/roles | EXISTS (Stage 104 frozen) |
| Permissions `?role=` write + `#system`/`#custom` Shell leaves | PARTIAL — read-once URL, no write / section anchors |
| Stores FEFO / reorder Shell + anchors (+ optional `store_id`) | MISSING — UI exists; only warehouses/transfers deep-linked |
| Platform audit/activity shareable filter URL | MISSING — tenant Audit already synced (Stage 102) |
| POS Hold/Resume / ADR-002 / ADR-005 / hard-delete | DEFERRED / OUT |

## Decision

1. **Stage 105 delivery track is open** per `docs/STAGE_105_PLAN.md`.
2. **Stage 1–104 freezes remain** for their respective scopes (Stage 104 under ADR-215).
3. Deliver Stage 105 **one workstream at a time** (P1 → S1 → A1 → D1 → H105x).
4. Explicitly out of this pass: paid billing / fabricated MRR / checkout / `subscriptions_live_claimed` Complete (ADR-002); User↔Store membership Complete (ADR-005); hard-delete Complete (ADR-003); impersonation; POS Hold/Resume; full Billers CRUD; parallel Income; WYSIWYG; fiscal-period close; reopening Stages 80–104 frozen scopes; main `ci.yml` deploy jobs. Honesty flags stay false.
5. Extend proven Shell deep-links, URL query sync, and page hash scroll — do not invent parallel stacks.
6. Main `ci.yml` remains deploy-free (**Stage 18 C1**).

## Consequences

- Agents may implement Stage 105 plan items without reopening Stage 1–104 feature scope.
- Stage 105 exit requires `docs/STAGE_105_EXIT_CRITERIA.md` with no CRITICAL/MISSING rows for planned workstreams.
