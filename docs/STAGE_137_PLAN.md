# Stage 137 Plan — Tenant MVP Stock Movements CSV, Low-Stock Alert CSV & Expiring Batches CSV Export Fidelity

**Status:** Closed — exit met (H137x); freeze ADR-281  
**Base:** Stock Movements CSV + Low-Stock Alert CSV + Expiring Batches CSV → Tenant MVP Stock Movements CSV, Low-Stock Alert CSV & Expiring Batches CSV Export Fidelity  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Open ADR:** [ADR-280](ADR_280_STAGE137_OPEN.md)  
**Exit:** [STAGE_137_EXIT_CRITERIA.md](STAGE_137_EXIT_CRITERIA.md) · freeze [ADR-281](ADR_281_STAGE137_FREEZE.md)  
**Fidelity:** [STAGE_137_FIDELITY.md](STAGE_137_FIDELITY.md)  
**Prior freeze:** [ADR-279](ADR_279_STAGE136_FREEZE.md) · [STAGE_136_EXIT_CRITERIA.md](STAGE_136_EXIT_CRITERIA.md)

## Delivery packs (derived)

```
Stock Movements CSV Pack
        +
Low-Stock Alert CSV Pack
        +
Expiring Batches CSV Pack
        ↓
Tenant MVP Stock Movements CSV, Low-Stock Alert CSV & Expiring Batches CSV Export Fidelity
```

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **M1** | Stock movements CSV honoring filters + Inventory UI | P0 | COMPLETE |
| **L1** | Low-stock status filter + CSV + Shell leaves | P0 | COMPLETE |
| **E1** | Expiring batches CSV + days UI + Shell leaves | P0 | COMPLETE |
| **D1** | Spec / readiness / launch / deploy / security fidelity sync | P1 | COMPLETE |
| **H137x** | Stage 137 exit criteria + freeze ADR | Exit | COMPLETE |

## Explicitly out of this pass

- Paid billing Complete (ADR-002); User↔Store membership (ADR-005); Hard-delete Complete (ADR-003)
- Impersonation; POS Hold/Resume; Billers CRUD; parallel Income; WYSIWYG Complete; PO OCR
- Admin remote-revoke-others; API-key un-revoke; FX soft-`is_active`
- Main `ci.yml` deploy; reopen Stages 1–136; Reports `/reports/export` reopen
- Payment allocation line dumps

## M1 acceptance criteria

- [x] `GET /inventory/movements/export` honoring filters; Inventory Export movements CSV.
- [x] Automated proof: `backend/tests/test_stage137_movements_export_m1.py`.

## L1 acceptance criteria

- [x] `GET /inventory/low-stock?stock_status=` + `/export`; Inventory filter + Shell Red/Yellow leaves.
- [x] Automated proof: `backend/tests/test_stage137_low_stock_l1.py`.

## E1 acceptance criteria

- [x] `GET /inventory/batches/expiring/export?days=`; Inventory Export + Shell expiry-days leaves.
- [x] Automated proof: `backend/tests/test_stage137_expiring_batches_e1.py`.

## D1 / H137x acceptance criteria

- [x] `docs/STAGE_137_FIDELITY.md` + exit/freeze ADR-281.
- [x] Automated proof: `test_stage137_fidelity_d1.py`, `test_stage137_exit_h137x.py`.
