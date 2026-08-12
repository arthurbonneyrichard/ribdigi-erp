# Stage 120 Plan — Tenant MVP Inactive Products, Users CSV Export & Expenses CSV Export Fidelity

**Status:** Closed — exit met (H120x); freeze ADR-247  
**Base:** Inactive Products Honesty + Users CSV Export + Expenses CSV Export → Tenant MVP Inactive Products, Users CSV Export & Expenses CSV Export Fidelity  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Open ADR:** [ADR-246](ADR_246_STAGE120_OPEN.md)  
**Exit:** [STAGE_120_EXIT_CRITERIA.md](STAGE_120_EXIT_CRITERIA.md) · freeze [ADR-247](ADR_247_STAGE120_FREEZE.md)  
**Fidelity:** [STAGE_120_FIDELITY.md](STAGE_120_FIDELITY.md)  
**Prior freeze:** [ADR-245](ADR_245_STAGE119_FREEZE.md) · [STAGE_119_EXIT_CRITERIA.md](STAGE_119_EXIT_CRITERIA.md)

## Delivery packs (derived)

```
Inactive Products Honesty Pack
        +
Users CSV Export Pack
        +
Expenses CSV Export Pack
        ↓
Tenant MVP Inactive Products, Users CSV Export & Expenses CSV Export Fidelity
```

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **P1** | Inactive products `active_only` / `is_active` honesty + UI/Shell | P0 | COMPLETE |
| **U1** | Users CSV export (`GET /users/export`) | P0 | COMPLETE |
| **X1** | Expenses CSV export (`GET /expenses/export`) | P0 | COMPLETE |
| **D1** | Spec / readiness / launch / deploy / security fidelity sync | P1 | COMPLETE |
| **H120x** | Stage 120 exit criteria + freeze ADR | Exit | COMPLETE |

## Explicitly out of this pass

- Paid billing / fabricated MRR / checkout / `subscriptions_live_claimed` Complete (ADR-002)
- User↔Store membership Complete (ADR-005)
- Hard-delete archival Complete (ADR-003)
- Impersonation; POS Hold/Resume; full Billers CRUD; parallel Income; WYSIWYG designer Complete
- PO OCR apply; year-end tax wizard / multi-book / GDPR DSAR portal Complete
- Reopening Stages 80–119 frozen feature scopes; main `ci.yml` deploy jobs

## P1 acceptance criteria

- [x] `GET /products?active_only=true` and `?is_active=true|false`; Inventory Products Active/Inactive filter; Shell Active/Inactive Products leaves.
- [x] Automated proof: `backend/tests/test_stage120_inactive_products_p1.py`.

## U1 acceptance criteria

- [x] `GET /users/export` tenant-scoped CSV (import-aligned columns + `is_active`; no passwords); Users Export button.
- [x] Automated proof: `backend/tests/test_stage120_users_export_u1.py`.

## X1 acceptance criteria

- [x] `GET /expenses/export` tenant-scoped CSV (record-scope aware); Expenses Export button.
- [x] Automated proof: `backend/tests/test_stage120_expenses_export_x1.py`.

## D1 / H120x acceptance criteria

- [x] `docs/STAGE_120_FIDELITY.md` + exit/freeze ADR-247.
- [x] Automated proof: `test_stage120_fidelity_d1.py`, `test_stage120_exit_h120x.py`.
