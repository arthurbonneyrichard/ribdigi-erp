# Stage 17 Fidelity Notes — Inventory Catalog & Stock Ops

**Status:** Closed with Stage 17 D1; exit met (H17x / ADR-040)  
**Surface:** Inventory → Catalog → Stock Ops → Warehouse → Low Stock  
**Open ADR (historical):** [ADR-039](ADR_039_STAGE17_OPEN.md)  
**Exit:** [STAGE_17_EXIT_CRITERIA.md](STAGE_17_EXIT_CRITERIA.md) · [ADR-040](ADR_040_STAGE17_FREEZE.md)  
**Plan:** [STAGE_17_PLAN.md](STAGE_17_PLAN.md)

Stage 17 proves commercial-MVP fidelity on the existing Inventory engine (Stage 2 I1–I6) — BR-5.1–5.5 live API/UI evidence, warehouse transfer + low-stock reorder-PO, and product/stock domain audit — **not** multi-bin, FIFO/LIFO/WA, ADR-005 user↔store membership, WebSocket push, or greenfield Inventory.

## Corrections applied

| Area | Before | After |
|------|--------|-------|
| BR-5.1 catalog | Checkbox drift vs Stage 2 I1–I6 | Marked via C1 live HTTP/UI proof |
| BR-5.2 stock ops | Mixed Stage 2/15 marks; count/transfer gaps | Stock In/Adjust/Opening (S1); Stock Count (S2); Stock Transfer (W1); Stock Out remains Stage 15 |
| BR-5.3 movements | All unchecked | Log/filter/export/immutable marked (Stage 2 I5 + reports export; D1 sync) |
| BR-5.4 warehouse | View/transfer Partial; reorder unchecked | View/transfer (W1); warehouse reorder policy (L1); valuation Stage 9 R2 |
| BR-5.5 low stock | All unchecked | Thresholds, traffic lights, suggestions/reorder-PO (L1); notifications Stage 16 N1 |
| BR-17.1 Product Changes | Unchecked | `product_create` / `product_update` / soft-delete `product_deactivate` + `stock_*` before/after (A1) |
| API §5.4 Products | Documented hard `DELETE` | Soft-deactivate via `PATCH is_active=false`; A1 audit note |
| API §5.8–5.9 Low stock | Nested `items` shape; fictional `/stock-levels` | Live array + `reorder-po`; product PATCH / store reorder-policy (L1) |
| USER_MANUAL §3.4 | “Generate Purchase Suggestion” → Purchase Request | Create draft PO from Low stock tab (L1) |
| USER_MANUAL §3.2 Stock Count | Generic steps | Match S2 complete → variance export flow |

## Workstream → evidence → BR → remaining

| WS | Evidence | BR mapping | Remaining |
|----|----------|------------|-----------|
| **C1** | `test_catalog_fidelity_c1.py` — categories tree, brands+logo, UoM convert, variants, barcode, images, batch/expiry | BR-5.1 | — |
| **S1** | `test_stock_ops_chain_s1.py` — stock-in → warehouse qty + movements; adjust reasons; opening stock | BR-5.2 In/Adjust/Opening | — |
| **S2** | `test_stock_count_chain_s2.py` — count → complete posts adjustments; variance CSV/PDF; immutable completed | BR-5.2 Stock Count | — |
| **W1** | `test_warehouse_transfer_chain_w1.py` — warehouse-stock grid; ship/receive; `409 INSUFFICIENT_WAREHOUSE_STOCK` | BR-5.2 Transfer; BR-5.4 view/transfer | Multi-bin |
| **L1** | `test_low_stock_reorder_l1.py` — traffic lights; `suggested_order_qty`; draft reorder-PO; store reorder-policy | BR-5.4 warehouse reorder; BR-5.5 | — |
| **A1** | `test_inventory_audit_a1.py` — product create/update/deactivate before/after; `stock_*` qty audits | BR-17.1 Product Changes | — |
| **D1** | This note + `test_stage17_fidelity_d1.py` | BR-5.1–5.5 + API + readiness + USER_MANUAL | — |
| **H17x** | `STAGE_17_EXIT_CRITERIA.md`; ADR-040; `test_stage17_exit_h17x.py` | Stage 17 exit + freeze | Next track needs open ADR |

## Evidence tests

- `backend/tests/test_catalog_fidelity_c1.py`
- `backend/tests/test_stock_ops_chain_s1.py`
- `backend/tests/test_stock_count_chain_s2.py`
- `backend/tests/test_warehouse_transfer_chain_w1.py`
- `backend/tests/test_low_stock_reorder_l1.py`
- `backend/tests/test_inventory_audit_a1.py`
- `backend/tests/test_stock_integrity_i5.py` (BR-5.3 movement before/after + filters)
- `backend/tests/test_stage2_inventory_ops.py` (movement date filters; reorder-PO Stage 2)
- `backend/tests/test_stage17_fidelity_d1.py`
- `backend/tests/test_stage17_exit_h17x.py`

## Spec sync targets

- `docs/BUSINESS_REQUIREMENTS_DOCUMENT.md` — BR-5.1–5.5, BR-17.1 Product Changes
- `docs/API_DOCUMENTATION.md` — §5 Inventory (C1–A1 notes)
- `docs/SECURITY_GUIDE.md` — Stage 17 A1 inventory domain audit
- `PRODUCTION_READINESS.md` — Inventory advanced bullet + Stage 17 D1
- `docs/USER_MANUAL.md` — §3 Inventory (C1–L1)
- `docs/DEVELOPMENT_ROADMAP.md` — Stage 17 D1 note
- `docs/LAUNCH_CHECKLIST.md` — C1–A1 / D1 evidence
- `docs/STAGE_17_PLAN.md` — Closed (H17x / ADR-040)
- `docs/STAGE_17_EXIT_CRITERIA.md` · `docs/ADR_040_STAGE17_FREEZE.md`

## Deferred (not Stage 17)

- Multi-bin / advanced locations
- FIFO/LIFO/WA costing
- User↔store membership (ADR-005)
- WebSocket realtime notification push
- Kubernetes / WAL / S3 PITR; PgBouncer; vendor pen test; certified 1000-VU
- Paid billing (ADR-002); schema-per-tenant (ADR-001); i18n (ADR-006)
- Native Open Banking; tax e-file portals
- PO Kanban (Stage 2 P2 deferred); Prophet/LLM upgrades
- Reopening Stage 2 I1–I6 or Stage 9–16 frozen feature scopes
