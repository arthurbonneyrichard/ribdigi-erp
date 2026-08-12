# Stage 133 Plan — Tenant MVP Sales Quotation CSV, Sales Order CSV & Sales Return CSV Export Fidelity

**Status:** Closed — exit met (H133x); freeze ADR-273  
**Base:** Quotation CSV + Order CSV + Return CSV → Tenant MVP Sales Quotation CSV, Sales Order CSV & Sales Return CSV Export Fidelity  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Open ADR:** [ADR-272](ADR_272_STAGE133_OPEN.md)  
**Exit:** [STAGE_133_EXIT_CRITERIA.md](STAGE_133_EXIT_CRITERIA.md) · freeze [ADR-273](ADR_273_STAGE133_FREEZE.md)  
**Fidelity:** [STAGE_133_FIDELITY.md](STAGE_133_FIDELITY.md)  
**Prior freeze:** [ADR-271](ADR_271_STAGE132_FREEZE.md) · [STAGE_132_EXIT_CRITERIA.md](STAGE_132_EXIT_CRITERIA.md)

## Delivery packs (derived)

```
Sales Quotation CSV Pack
        +
Sales Order CSV Pack
        +
Sales Return CSV Pack
        ↓
Tenant MVP Sales Quotation CSV, Sales Order CSV & Sales Return CSV Export Fidelity
```

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **Q1** | Sales quotation header CSV honoring status + Sales UI | P0 | COMPLETE |
| **O1** | Sales order header CSV honoring status + Sales UI | P0 | COMPLETE |
| **R1** | Sales return header CSV honoring status + Sales UI | P0 | COMPLETE |
| **D1** | Spec / readiness / launch / deploy / security fidelity sync | P1 | COMPLETE |
| **H133x** | Stage 133 exit criteria + freeze ADR | Exit | COMPLETE |

## Explicitly out of this pass

- Paid billing Complete (ADR-002); User↔Store membership (ADR-005); Hard-delete Complete (ADR-003)
- Impersonation; POS Hold/Resume; Billers CRUD; parallel Income; WYSIWYG Complete; PO OCR
- Admin remote-revoke-others; API-key un-revoke; FX soft-`is_active`
- Main `ci.yml` deploy; reopen Stages 1–132
- Line dumps; purchasing pipeline CSVs (PR/PO/GRN/returns); payment tenant lists; SMS settings CSV

## Q1 acceptance criteria

- [x] `GET /sales/quotations/export` honoring status; Sales Export quotations CSV button.
- [x] Automated proof: `backend/tests/test_stage133_quotations_export_q1.py`.

## O1 acceptance criteria

- [x] `GET /sales/orders/export` honoring status; Sales Export orders CSV button.
- [x] Automated proof: `backend/tests/test_stage133_orders_export_o1.py`.

## R1 acceptance criteria

- [x] `GET /sales/returns/export` honoring status; Sales Export returns CSV button.
- [x] Automated proof: `backend/tests/test_stage133_returns_export_r1.py`.

## D1 / H133x acceptance criteria

- [x] `docs/STAGE_133_FIDELITY.md` + exit/freeze ADR-273.
- [x] Automated proof: `test_stage133_fidelity_d1.py`, `test_stage133_exit_h133x.py`.
