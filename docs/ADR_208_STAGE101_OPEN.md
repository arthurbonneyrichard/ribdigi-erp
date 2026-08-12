# ADR-208: Stage 101 Delivery Track Opened

**Status:** Accepted  
**Date:** 2026-08-12  
**Supersedes (in part):** ADR-207 clause that blocked opening the next delivery track until explicit sign-off

## Context

Stage 100 Tenant MVP Reports & Ledger Discovery Ops exit criteria are met (`docs/STAGE_100_EXIT_CRITERIA.md`) with R1–U1 / D1 / H100x Complete (ADR-207). Product owner approved opening Stage 101 after Stage 100 freeze via CONTINUE/NEXT with a distinct product outline — remaining **inventory ops & shift history honesty** (Opening Stock / Movements Shell, Recurring Expenses leaf + notification deep-links, POS session history UI), not another reports/GL/admin-discovery pass:

```
Opening Stock & Movements Shell Discoverability
     ↓
Recurring Expenses Leaf & Notification Deep-Link Honesty
     ↓
POS Session History Discoverability
     ↓
Tenant MVP Inventory Ops & Shift History Ops
```

Audit after Stage 100 found:

| Area | Status |
|------|--------|
| Reports statements / GL COA·journals·TB / tenant users·audit URL sync | EXISTS (Stage 100 frozen) |
| Inventory Opening / Movements tabs exist; Shell leaves missing; Catalog Categories lacks `#categories` | PARTIAL |
| Recurring expenses UI + APIs exist; Shell Pending / Approval Matrix only; notify deep-links land on bare `/expenses` | PARTIAL |
| `GET /pos/sessions` + shift report APIs exist; no session-history UI / Shell leaf | MISSING |
| POS Hold/Resume / ADR-002 / ADR-005 / hard-delete | DEFERRED / OUT |

## Decision

1. **Stage 101 delivery track is open** per `docs/STAGE_101_PLAN.md`.
2. **Stage 1–100 freezes remain** for their respective scopes (Stage 100 under ADR-207).
3. Deliver Stage 101 **one workstream at a time** (O1 → E1 → P1 → D1 → H101x).
4. Explicitly out of this pass: paid billing / fabricated MRR / checkout / `subscriptions_live_claimed` Complete (ADR-002); User↔Store membership Complete (ADR-005); hard-delete Complete (ADR-003); impersonation; **POS Hold/Resume**; full Billers CRUD; parallel Income module; WYSIWYG designer; fiscal-period close console; reopening Stages 80–100 frozen scopes; main `ci.yml` deploy jobs. Honesty flags stay false.
5. Extend proven inventory tabs, expenses recurring section, notifications filters, and POS session APIs — do not invent parallel stacks.
6. Main `ci.yml` remains deploy-free (**Stage 18 C1**).

## Consequences

- Agents may implement Stage 101 plan items without reopening Stage 1–100 feature scope.
- Stage 101 exit requires `docs/STAGE_101_EXIT_CRITERIA.md` with no CRITICAL/MISSING rows for planned workstreams.
