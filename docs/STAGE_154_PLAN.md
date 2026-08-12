# Stage 154 Plan — Tenant MVP PO Amendments CSV, Product Batches CSV & API-Key Usage CSV Export Fidelity

**Status:** Closed — exit met (H154x); freeze ADR-315  
**Base:** PO Amendments CSV + Product Batches CSV + API-Key Usage CSV → Tenant MVP PO Amendments CSV, Product Batches CSV & API-Key Usage CSV Export Fidelity  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Open ADR:** [ADR-314](ADR_314_STAGE154_OPEN.md)  
**Exit:** [STAGE_154_EXIT_CRITERIA.md](STAGE_154_EXIT_CRITERIA.md) · freeze [ADR-315](ADR_315_STAGE154_FREEZE.md)  
**Fidelity:** [STAGE_154_FIDELITY.md](STAGE_154_FIDELITY.md)  
**Prior freeze:** [ADR-313](ADR_313_STAGE153_FREEZE.md) · [STAGE_153_EXIT_CRITERIA.md](STAGE_153_EXIT_CRITERIA.md)

## Delivery packs (derived)

```
PO Amendments CSV Pack
        +
Product Batches CSV Pack
        +
API-Key Usage CSV Pack
        ↓
Tenant MVP PO Amendments CSV, Product Batches CSV & API-Key Usage CSV Export Fidelity
```

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **A1** | PO amendments CSV + Purchasing UI | P0 | COMPLETE |
| **K1** | Product batches CSV + Inventory Batches UI | P0 | COMPLETE |
| **U1** | API-key usage CSV + Security UI | P0 | COMPLETE |
| **D1** | Spec / readiness / launch / deploy / security fidelity sync | P1 | COMPLETE |
| **H154x** | Stage 154 exit criteria + freeze ADR | Exit | COMPLETE |

## Explicitly out of this pass

- Paid billing Complete (ADR-002); User↔Store membership (ADR-005); Hard-delete Complete (ADR-003)
- Fabricated MRR; live subscriptions; checkout Complete
- Impersonation; POS Hold/Resume; Billers CRUD; parallel Income; WYSIWYG Complete; PO OCR
- Admin remote-revoke-others; API-key un-revoke; FX soft-`is_active`
- Main `ci.yml` deploy; reopen Stages 1–153
- External LLM Complete; Stage 137 expiring batches reopen; Stage 127 API-keys roster reopen

## A1 acceptance criteria

- [x] `GET /purchasing/orders/{id}/amendments/export`; Purchasing Export amendments CSV.
- [x] Automated proof: `backend/tests/test_stage154_po_amendments_a1.py`.

## K1 acceptance criteria

- [x] `GET /products/{id}/batches/export`; Inventory Export product batches CSV.
- [x] Automated proof: `backend/tests/test_stage154_product_batches_k1.py`.

## U1 acceptance criteria

- [x] `GET /api-keys/{id}/usage/export`; Security Export usage CSV.
- [x] Automated proof: `backend/tests/test_stage154_api_key_usage_u1.py`.

## D1 / H154x acceptance criteria

- [x] `docs/STAGE_154_FIDELITY.md` + exit/freeze ADR-315.
- [x] Automated proof: `test_stage154_fidelity_d1.py`, `test_stage154_exit_h154x.py`.
