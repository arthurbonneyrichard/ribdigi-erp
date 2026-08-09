# Stage 2 Plan — Inventory & Supply Chain Hardening

**Status:** Open (ADR-009)  
**Base:** Phase 2 roadmap (`docs/DEVELOPMENT_ROADMAP.md` §3) + BR-5.x / BR-6.x  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  

Stage 2 here is **not** a rewrite of inventory/purchasing. Core engines (catalog, stock movements, transfers, counts, low-stock reorder PO, suppliers, PR→PO→GRN→invoice→return) already exist. This plan closes remaining BR acceptance holes and UI gaps, then freezes Stage 2.

## Delivery rules

1. One workstream at a time (full AC + automated tests before the next).
2. Prefer extending proven patterns (`apply_stock_change`, stock CSV import, Counts scanner, reports export).
3. No demo data / fake success. Alembic for any schema change.
4. After each feature: tests → commit → push → PR update.

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **I1** | Dedicated opening stock entry (API + UI + bulk) | P0 | COMPLETE |
| **I2** | Stock ops barcode scan + adjustment reason codes | P0 | COMPLETE |
| **I3** | Low stock: `minimum_stock` + traffic lights + warehouse-aware list | P0 | PENDING |
| **I4** | Stock count variance report export (CSV/PDF) | P0 | PENDING |
| **I5** | Movement history audit UX + integrity/concurrency tests | P1 | PENDING |
| **I6** | Catalog harden: UoM conversion, brand logo, weight/dimensions | P1 | PENDING |
| **P1** | Purchase return multi-line UI | P1 | PENDING |
| **P2** | PO Kanban board (optional polish) | P2 | DEFERRED unless pulled |
| **M1** | Multi-bin locations | Multi-store | OUT OF SCOPE (this pass) |
| **H2** | Stage 2 exit criteria + freeze ADR | Exit | PENDING |

## Explicitly out of this pass

- Paid billing provider (ADR-002)
- Multi-language packs (ADR-006)
- Schema-per-tenant (ADR-001)
- Native Open Banking / Plaid adapters
- Advanced multi-bin (M1)

## I1 acceptance criteria

- [x] `POST /inventory/opening-stock` records `opening_stock` movements for existing products (optional warehouse / variant / batch).
- [x] Supports `mode=add` (default) and `mode=set` (absolute target; cannot reduce — use adjust/count).
- [x] Multi-line payload for go-live / fiscal start bulk.
- [x] Inventory UI **Opening** tab for single-line entry; stock CSV may use `mode=opening`.
- [x] Tenant + RBAC (`inventory` write); automated tests in `backend/tests/test_opening_stock_i1.py`.

## I2 acceptance criteria

- [x] Stock ops tab: barcode/camera lookup selects product.
- [x] Adjustment reason enum: damage / theft / expiry / found / lost / other (`stock_movements.reason`, Alembic `0072`).
- [x] Automated tests in `backend/tests/test_stock_ops_i2.py`.

## I3 acceptance criteria (next)

- [ ] Product (+ warehouse where set) `minimum_stock` alongside `reorder_level`.
- [ ] Low-stock / catalog traffic-light status (green / yellow / red).
- [ ] Low-stock list warehouse-aware; Celery/scan uses dual thresholds.
- [ ] Automated tests for thresholds + status.

## Sign-off

Stage 2 opens with ADR-009. Close when all P0 rows are COMPLETE and `docs/STAGE_2_EXIT_CRITERIA.md` is accepted.
