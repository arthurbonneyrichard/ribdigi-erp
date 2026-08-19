# Stage 134 Plan — Tenant MVP Purchase Request CSV, Purchase Order CSV & GRN CSV Export Fidelity

**Status:** Closed — exit met (H134x); freeze ADR-275  
**Base:** Purchase Request CSV + Purchase Order CSV + GRN CSV → Tenant MVP Purchase Request CSV, Purchase Order CSV & GRN CSV Export Fidelity  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Open ADR:** [ADR-274](ADR_274_STAGE134_OPEN.md)  
**Exit:** [STAGE_134_EXIT_CRITERIA.md](STAGE_134_EXIT_CRITERIA.md) · freeze [ADR-275](ADR_275_STAGE134_FREEZE.md)  
**Fidelity:** [STAGE_134_FIDELITY.md](STAGE_134_FIDELITY.md)  
**Prior freeze:** [ADR-273](ADR_273_STAGE133_FREEZE.md) · [STAGE_133_EXIT_CRITERIA.md](STAGE_133_EXIT_CRITERIA.md)

## Delivery packs (derived)

```
Purchase Request CSV Pack
        +
Purchase Order CSV Pack
        +
GRN CSV Pack
        ↓
Tenant MVP Purchase Request CSV, Purchase Order CSV & GRN CSV Export Fidelity
```

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **R1** | Purchase request header CSV honoring status + Purchasing UI | P0 | COMPLETE |
| **O1** | Purchase order header CSV honoring status + Purchasing UI | P0 | COMPLETE |
| **G1** | GRN header CSV honoring status + Purchasing UI | P0 | COMPLETE |
| **D1** | Spec / readiness / launch / deploy / security fidelity sync | P1 | COMPLETE |
| **H134x** | Stage 134 exit criteria + freeze ADR | Exit | COMPLETE |

## Explicitly out of this pass

- Paid billing Complete (ADR-002); User↔Store membership (ADR-005); Hard-delete Complete (ADR-003)
- Impersonation; POS Hold/Resume; Billers CRUD; parallel Income; WYSIWYG Complete; PO OCR
- Admin remote-revoke-others; API-key un-revoke; FX soft-`is_active`
- Main `ci.yml` deploy; reopen Stages 1–133
- Line dumps; purchase-return CSV; payment tenant lists; SMS settings CSV

## R1 acceptance criteria

- [x] `GET /purchasing/requests/export` honoring status; Purchasing Export requests CSV button.
- [x] Automated proof: `backend/tests/test_stage134_requests_export_r1.py`.

## O1 acceptance criteria

- [x] `GET /purchasing/orders/export` honoring status; Purchasing Export orders CSV button.
- [x] Automated proof: `backend/tests/test_stage134_orders_export_o1.py`.

## G1 acceptance criteria

- [x] `GET /purchasing/grn/export` honoring status; Purchasing Export GRNs CSV button.
- [x] Automated proof: `backend/tests/test_stage134_grn_export_g1.py`.

## D1 / H134x acceptance criteria

- [x] `docs/STAGE_134_FIDELITY.md` + exit/freeze ADR-275.
- [x] Automated proof: `test_stage134_fidelity_d1.py`, `test_stage134_exit_h134x.py`.
