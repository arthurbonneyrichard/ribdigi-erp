# Stage 136 Plan — Tenant MVP Customer Payment Register CSV, Supplier Payment Register CSV & Credit Aging CSV Export Fidelity

**Status:** Closed — exit met (H136x); freeze ADR-279  
**Base:** Customer Payment CSV + Supplier Payment CSV + Credit Aging CSV → Tenant MVP Customer Payment Register CSV, Supplier Payment Register CSV & Credit Aging CSV Export Fidelity  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Open ADR:** [ADR-278](ADR_278_STAGE136_OPEN.md)  
**Exit:** [STAGE_136_EXIT_CRITERIA.md](STAGE_136_EXIT_CRITERIA.md) · freeze [ADR-279](ADR_279_STAGE136_FREEZE.md)  
**Fidelity:** [STAGE_136_FIDELITY.md](STAGE_136_FIDELITY.md)  
**Prior freeze:** [ADR-277](ADR_277_STAGE135_FREEZE.md) · [STAGE_135_EXIT_CRITERIA.md](STAGE_135_EXIT_CRITERIA.md)

## Delivery packs (derived)

```
Customer Payment Register CSV Pack
        +
Supplier Payment Register CSV Pack
        +
Credit Aging CSV Pack
        ↓
Tenant MVP Customer Payment Register CSV, Supplier Payment Register CSV & Credit Aging CSV Export Fidelity
```

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **C1** | Customer payment list + header CSV + Credit UI | P0 | COMPLETE |
| **S1** | Supplier payment list + header CSV + Credit UI | P0 | COMPLETE |
| **A1** | Aging document CSV honoring kind + Credit UI | P0 | COMPLETE |
| **D1** | Spec / readiness / launch / deploy / security fidelity sync | P1 | COMPLETE |
| **H136x** | Stage 136 exit criteria + freeze ADR | Exit | COMPLETE |

## Explicitly out of this pass

- Paid billing Complete (ADR-002); User↔Store membership (ADR-005); Hard-delete Complete (ADR-003)
- Impersonation; POS Hold/Resume; Billers CRUD; parallel Income; WYSIWYG Complete; PO OCR
- Admin remote-revoke-others; API-key un-revoke; FX soft-`is_active`
- Main `ci.yml` deploy; reopen Stages 1–135
- Payment allocation line dumps; statement PDF batch

## C1 acceptance criteria

- [x] `GET /credit/customer-payments` + `/export` with optional filters; Credit Export customer payments CSV.
- [x] Automated proof: `backend/tests/test_stage136_customer_payments_c1.py`.

## S1 acceptance criteria

- [x] `GET /credit/supplier-payments` + `/export` with optional filters; Credit Export supplier payments CSV.
- [x] Automated proof: `backend/tests/test_stage136_supplier_payments_s1.py`.

## A1 acceptance criteria

- [x] `GET /credit/aging/export?kind=` document rows; Credit Export aging CSV.
- [x] Automated proof: `backend/tests/test_stage136_aging_export_a1.py`.

## D1 / H136x acceptance criteria

- [x] `docs/STAGE_136_FIDELITY.md` + exit/freeze ADR-279.
- [x] Automated proof: `test_stage136_fidelity_d1.py`, `test_stage136_exit_h136x.py`.
