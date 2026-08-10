# Stage 17 Plan — Inventory Catalog & Stock Ops Fidelity

**Status:** Closed — exit met (H17x / ADR-040)  
**Base:** Inventory → Catalog → Stock Ops → Warehouse → Low Stock  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Open ADR (historical):** [ADR-039](ADR_039_STAGE17_OPEN.md)  
**Exit:** [STAGE_17_EXIT_CRITERIA.md](STAGE_17_EXIT_CRITERIA.md) · [ADR-040](ADR_040_STAGE17_FREEZE.md) · [STAGE_17_FIDELITY.md](STAGE_17_FIDELITY.md)

Stage 17 closes commercial-MVP fidelity on the Inventory surface after Stage 16 freeze. The Stage 2 catalog/stock engine already exists (I1–I6). This track proves BR-5.1–5.5 end-to-end with live APIs/UI evidence and docs sync — **not** multi-bin, FIFO/LIFO, or greenfield Inventory.

## Product outline (owner)

```
Inventory
 ├── Catalog (Categories · Brands · Units · Variants · Barcode · Images · Batch/Expiry)
 ├── Stock Operations (Stock In · Stock Out · Adjustment · Opening Stock · Stock Count)
 ├── Warehouse Stock (Per-location qty · Reorder levels · Inter-warehouse transfer)
 └── Low Stock (Traffic lights · Alerts · Purchase suggestions / reorder-PO)
```

## Delivery rules

1. One workstream at a time (full AC + automated tests before the next).
2. Prefer extending proven Stage 2 patterns (`catalog_meta`, `apply_stock_change`, stock counts, low-stock reorder-PO).
3. No demo data / fake success. Alembic only when schema is required.
4. After each feature: tests → commit → push → PR update.
5. Do not reopen Stage 1–16 feature scopes; do not rewrite the Inventory engine.

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **C1** | Catalog fidelity proof (categories/brands/UoM/variants/barcode/images/batch-expiry) | P0 | COMPLETE |
| **S1** | Stock ops chain (stock-in → movements → warehouse qty; adjust reasons; opening stock) | P0 | COMPLETE |
| **S2** | Stock count → variance report → post adjustments | P0 | COMPLETE |
| **W1** | Warehouse stock grid + inter-warehouse transfer ship/receive chain | P1 | COMPLETE |
| **L1** | Low-stock indicators + suggested order qty + reorder-PO | P1 | COMPLETE |
| **A1** | Inventory domain audit closeout (product/stock mutations) | P1 | COMPLETE |
| **D1** | Spec / BR-5.1–5.5 / readiness fidelity sync | P2 | COMPLETE |
| **H17x** | Stage 17 exit criteria + freeze ADR | Exit | COMPLETE |

## Explicitly out of this pass

- Kubernetes / Helm; Prometheus/Grafana/PagerDuty; PgBouncer
- pg_dump / WAL / S3 offsite PITR; vendor pen test; certified 1000-VU
- Paid billing (ADR-002); schema-per-tenant (ADR-001); i18n (ADR-006)
- Native Open Banking; tax authority e-file portals
- FIFO/LIFO/WA; multi-bin / advanced locations
- User↔store membership (ADR-005); WebSocket realtime notification push
- PO Kanban (Stage 2 P2 deferred); Prophet/LLM upgrades
- Reopening Stage 2 I1–I6 or Stage 9–16 frozen feature scopes

## C1 acceptance criteria

- [x] Live proof that hierarchical categories, brands (incl. description/logo path), UoM conversion, product create with FKs + details, variants with unique SKUs, barcode generate, multi-image primary, and batch/expiry via stock-in resolve through HTTP APIs (Catalog/Inventory UI surfaces present).
- [x] Tenant isolation on catalog/product reads.
- [x] Automated proof: `backend/tests/test_catalog_fidelity_c1.py`.

## S1 acceptance criteria

- [x] Stock-in → warehouse qty + `stock_movements`; adjustment with reason codes; opening stock path proven.
- [x] Automated proof for chosen ops chain: `backend/tests/test_stock_ops_chain_s1.py`.

## S2 acceptance criteria

- [x] Stock count create → enter counts → complete posts adjustments; variance report export; immutable completed counts.
- [x] Automated proof: `backend/tests/test_stock_count_chain_s2.py`.

## W1 acceptance criteria

- [x] Per-product warehouse stock view + inter-warehouse transfer ship/receive updates qty/movements (extend Stage 2 / Stage 16 patterns; not multi-bin).
- [x] Automated proof: `backend/tests/test_warehouse_transfer_chain_w1.py`.

## L1 acceptance criteria

- [x] Traffic-light / low-stock list + suggested order qty + draft reorder PO path proven.
- [x] Automated proof: `backend/tests/test_low_stock_reorder_l1.py`.

## A1 acceptance criteria

- [x] Domain audit events for key product/stock mutations (BR-17.1 Product Changes where applicable).
- [x] Automated proof: `backend/tests/test_inventory_audit_a1.py`.

## D1 acceptance criteria

- [x] BR-5.1–5.5, API, readiness, user manual aligned — `docs/STAGE_17_FIDELITY.md`.
- [x] Guard test: `backend/tests/test_stage17_fidelity_d1.py`.

## H17x acceptance criteria

- [x] `docs/STAGE_17_EXIT_CRITERIA.md` lists C1–A1, D1, H17x COMPLETE with evidence tests and deferred scope.
- [x] Freeze ADR accepted: `docs/ADR_040_STAGE17_FREEZE.md`.
- [x] Automated proof: `backend/tests/test_stage17_exit_h17x.py`.

## Sign-off

Stage 17 exit **met**. Scope frozen under ADR-040. Stages 1–16 remain frozen for their scopes. Next delivery track requires an explicit open ADR with a **distinct** product outline (Multi-Store / Reports / Notifications already closed under Stage 16 / ADR-038).
