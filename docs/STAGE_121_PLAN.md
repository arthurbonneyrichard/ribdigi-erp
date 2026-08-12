# Stage 121 Plan — Tenant MVP Inactive Stores & Warehouses & Location CSV Export Fidelity

**Status:** Closed — exit met (H121x); freeze ADR-249  
**Base:** Inactive Stores Honesty + Inactive Warehouses Honesty + Location CSV Export → Tenant MVP Inactive Stores & Warehouses & Location CSV Export Fidelity  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Open ADR:** [ADR-248](ADR_248_STAGE121_OPEN.md)  
**Exit:** [STAGE_121_EXIT_CRITERIA.md](STAGE_121_EXIT_CRITERIA.md) · freeze [ADR-249](ADR_249_STAGE121_FREEZE.md)  
**Fidelity:** [STAGE_121_FIDELITY.md](STAGE_121_FIDELITY.md)  
**Prior freeze:** [ADR-247](ADR_247_STAGE120_FREEZE.md) · [STAGE_120_EXIT_CRITERIA.md](STAGE_120_EXIT_CRITERIA.md)

## Delivery packs (derived)

```
Inactive Stores Honesty Pack
        +
Inactive Warehouses Honesty Pack
        +
Location CSV Export Pack
        ↓
Tenant MVP Inactive Stores & Warehouses & Location CSV Export Fidelity
```

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **S1** | Inactive stores `is_active` / `active_only` honesty + UI/Shell | P0 | COMPLETE |
| **W1** | Inactive warehouses `is_active` / `active_only` honesty + UI/Shell | P0 | COMPLETE |
| **X1** | Location CSV export (`GET /stores/export`, `/warehouses/export`, `/tax/rates/export`) | P0 | COMPLETE |
| **D1** | Spec / readiness / launch / deploy / security fidelity sync | P1 | COMPLETE |
| **H121x** | Stage 121 exit criteria + freeze ADR | Exit | COMPLETE |

## Explicitly out of this pass

- Paid billing / fabricated MRR / checkout / `subscriptions_live_claimed` Complete (ADR-002)
- User↔Store membership Complete (ADR-005)
- Hard-delete archival Complete (ADR-003)
- Impersonation; POS Hold/Resume; full Billers CRUD; parallel Income; WYSIWYG designer Complete
- PO OCR apply; percentage discount UI polish; year-end tax wizard / multi-book / GDPR DSAR portal Complete
- Reopening Stages 80–120 frozen feature scopes; main `ci.yml` deploy jobs

## S1 acceptance criteria

- [x] `GET /stores?is_active=true|false` (+ `active_only`); Stores Active/Inactive filter; Shell Active/Inactive Stores leaves.
- [x] Automated proof: `backend/tests/test_stage121_inactive_stores_s1.py`.

## W1 acceptance criteria

- [x] `GET /warehouses?is_active=true|false` (+ `active_only`); Stores warehouses Active/Inactive filter; Shell Active/Inactive Warehouses leaves.
- [x] Automated proof: `backend/tests/test_stage121_inactive_warehouses_w1.py`.

## X1 acceptance criteria

- [x] `GET /stores/export`, `GET /warehouses/export`, `GET /tax/rates/export`; Stores/Tax Export buttons.
- [x] Automated proof: `backend/tests/test_stage121_location_export_x1.py`.

## D1 / H121x acceptance criteria

- [x] `docs/STAGE_121_FIDELITY.md` + exit/freeze ADR-249.
- [x] Automated proof: `test_stage121_fidelity_d1.py`, `test_stage121_exit_h121x.py`.
