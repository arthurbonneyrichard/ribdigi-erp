# Stage 9 Documentation Fidelity (D1)

**Status:** Complete (Stage 9 exit met — ADR-024)  
**Related:** [STAGE_9_PLAN.md](STAGE_9_PLAN.md), [STAGE_9_EXIT_CRITERIA.md](STAGE_9_EXIT_CRITERIA.md), [ADR-023](ADR_023_STAGE9_OPEN.md), [ADR-024](ADR_024_STAGE9_FREEZE.md)  
**Guard:** `backend/tests/test_stage9_fidelity_d1.py`

This note records that Stage 9 delivered behavior is reflected in authoritative docs without overstating deferred work.

## Delivered (must appear as implemented)

| Workstream | Behavior | Primary docs |
|------------|----------|--------------|
| **J1** | Journal supporting documents (`attachment_url`; upload/download/delete) | BR-10.2, API §10.2, DATABASE `journal_entries`, USER_MANUAL §8.2 |
| **R1** | Pending POs + purchase return summary reports | BR-14.3, API §14.3, USER_MANUAL §12.4 |
| **R2** | Stock valuation at **standard cost** (`qty × product.cost_price`) | BR-14.2 / BR-5.4, API §14.2, USER_MANUAL §12.3 |

## Explicitly not claimed complete

- FIFO / LIFO / weighted-average inventory costing
- Kubernetes, WAL/PITR, vendor pen test, PgBouncer, certified 1000-VU
- Paid billing, schema-per-tenant, i18n packs, Open Banking, tax e-file

## Costing language rule

Docs must state valuation is **standard cost** (current `product.cost_price`). They must not describe FIFO/LIFO/WA as available. Changing `cost_price` recomputes valuation immediately (there is no historical cost layer).

## Related inventory report ACs (pre-existing, verified present)

Report APIs already exist and BR-14.2 checkboxes are aligned:

- Stock Balance — `GET /reports/inventory/balance`
- Low Stock — `GET /reports/inventory/low-stock`
- Stock Movement — `GET /reports/inventory/movements`
- Expiry Report — `GET /reports/inventory/expiry`
