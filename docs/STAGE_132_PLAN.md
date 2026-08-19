# Stage 132 Plan — Tenant MVP Sales Invoice Register CSV, Stock-Transfer List Export & Purchase Invoice Register Fidelity

**Status:** Closed — exit met (H132x); freeze ADR-271  
**Base:** Sales Invoice CSV + Stock-Transfer List Status & CSV + Purchase Invoice CSV → Tenant MVP Sales Invoice Register CSV, Stock-Transfer List Export & Purchase Invoice Register Fidelity  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Open ADR:** [ADR-270](ADR_270_STAGE132_OPEN.md)  
**Exit:** [STAGE_132_EXIT_CRITERIA.md](STAGE_132_EXIT_CRITERIA.md) · freeze [ADR-271](ADR_271_STAGE132_FREEZE.md)  
**Fidelity:** [STAGE_132_FIDELITY.md](STAGE_132_FIDELITY.md)  
**Prior freeze:** [ADR-269](ADR_269_STAGE131_FREEZE.md) · [STAGE_131_EXIT_CRITERIA.md](STAGE_131_EXIT_CRITERIA.md)

## Delivery packs (derived)

```
Sales Invoice Register CSV Pack
        +
Stock-Transfer List Status & CSV Pack
        +
Purchase Invoice Register CSV Pack
        ↓
Tenant MVP Sales Invoice Register CSV, Stock-Transfer List Export & Purchase Invoice Register Fidelity
```

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **I1** | Sales invoice header CSV honoring status + Sales UI | P0 | COMPLETE |
| **T1** | Stock-transfer list status honesty + CSV + UI/Shell | P0 | COMPLETE |
| **P1** | Purchase invoice header CSV honoring status + Purchasing UI | P0 | COMPLETE |
| **D1** | Spec / readiness / launch / deploy / security fidelity sync | P1 | COMPLETE |
| **H132x** | Stage 132 exit criteria + freeze ADR | Exit | COMPLETE |

## Explicitly out of this pass

- Paid billing Complete (ADR-002); User↔Store membership (ADR-005); Hard-delete Complete (ADR-003)
- Impersonation; POS Hold/Resume; Billers CRUD; parallel Income; WYSIWYG Complete; PO OCR
- Admin remote-revoke-others; API-key un-revoke; FX soft-`is_active`
- Main `ci.yml` deploy; reopen Stages 1–131
- Invoice/transfer line dump in CSV; customer/supplier payment tenant list APIs; sales quotations/orders/returns CSV

## I1 acceptance criteria

- [x] `GET /sales/invoices/export` honoring status; Sales Export invoices CSV button.
- [x] Automated proof: `backend/tests/test_stage132_sales_invoices_export_i1.py`.

## T1 acceptance criteria

- [x] `GET /inventory/stock-transfers?status=` + `GET /inventory/stock-transfers/export`; Inventory filter; Shell Draft/Requested/In-transit/Received/Cancelled Warehouse Transfers.
- [x] Automated proof: `backend/tests/test_stage132_stock_transfers_t1.py`.

## P1 acceptance criteria

- [x] `GET /purchasing/invoices/export` honoring status; Purchasing Export invoices CSV button.
- [x] Automated proof: `backend/tests/test_stage132_purchase_invoices_export_p1.py`.

## D1 / H132x acceptance criteria

- [x] `docs/STAGE_132_FIDELITY.md` + exit/freeze ADR-271.
- [x] Automated proof: `test_stage132_fidelity_d1.py`, `test_stage132_exit_h132x.py`.
