# ADR-338: Stage 166 Open — Offline Complete Hardening Fidelity

**Status:** Accepted  
**Date:** 2026-08-13  
**Related:** [ADR-337](ADR_337_STAGE165_FREEZE.md), [CHANGE_IMPACT_MVP_UPDATE_2026-08-13.md](CHANGE_IMPACT_MVP_UPDATE_2026-08-13.md), [STAGE_166_PLAN.md](STAGE_166_PLAN.md)

## Context

Stage 165 froze IndexedDB queue + Partial Hold/Resume + conflict resolve without re-apply (ADR-337). The approved runner-up outline hardens offline paths without claiming Offline Complete: stock-safe catalog cache, safe `accept_client` re-apply, and optional Hold soft stock reservation.

## Decision

Open **Stage 166 — Offline Complete Hardening Fidelity** with packs:

| Pack | Scope |
|------|--------|
| **C1** | Stock-safe offline catalog cache (IndexedDB from `/sync/pull`); stale stock honesty; POS search when offline |
| **A1** | Conflict `accept_client` re-apply policy — re-apply only when original op was never applied; never double-post applied POS |
| **S1** | Hold soft stock reservation — `product.reserved_qty` via `reserve_stock` (not SO `StockReservation` rows); Alembic `20260813_0094` |
| **D1 / H166x** | Fidelity cite sync + Stage 166 exit; freeze as **ADR-339** |

### Hold soft reservation ADR note (S1)

- Soft reserve increments `product.reserved_qty` under row lock; resume/discard releases.
- Does **not** create sales-order `StockReservation` rows (those require `sales_order_id`).
- Default `reserve_stock=false` preserves Stage 165 park-only behavior for existing clients/tests.
- Soft reserve is **not** Offline Complete and is not a sale.

## Consequences

- Does **not** claim Offline Complete, fabricated MRR, or ADR-002/003/005 Completes.
- Honesty flags stay false.
- Stages 1–165 feature scopes remain frozen (except documented supersession for accept_client re-apply policy).
