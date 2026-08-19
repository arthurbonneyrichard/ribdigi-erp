# Stage 122 Plan — Tenant MVP Inactive Org Units, Catalog Meta & Org/Catalog-Meta CSV Export Fidelity

**Status:** Closed — exit met (H122x); freeze ADR-251  
**Base:** Inactive Org Units Honesty + Inactive Catalog Meta Honesty + Org & Catalog-Meta CSV Export → Tenant MVP Inactive Org Units, Catalog Meta & Org/Catalog-Meta CSV Export Fidelity  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Open ADR:** [ADR-250](ADR_250_STAGE122_OPEN.md)  
**Exit:** [STAGE_122_EXIT_CRITERIA.md](STAGE_122_EXIT_CRITERIA.md) · freeze [ADR-251](ADR_251_STAGE122_FREEZE.md)  
**Fidelity:** [STAGE_122_FIDELITY.md](STAGE_122_FIDELITY.md)  
**Prior freeze:** [ADR-249](ADR_249_STAGE121_FREEZE.md) · [STAGE_121_EXIT_CRITERIA.md](STAGE_121_EXIT_CRITERIA.md)

## Delivery packs (derived)

```
Inactive Org Units Honesty Pack
        +
Inactive Catalog Meta Honesty Pack
        +
Org & Catalog-Meta CSV Export Pack
        ↓
Tenant MVP Inactive Org Units, Catalog Meta & Org/Catalog-Meta CSV Export Fidelity
```

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **O1** | Inactive branches/departments `is_active` / `active_only` honesty + UI/Shell | P0 | COMPLETE |
| **M1** | Inactive categories/brands/units `is_active` / `active_only` honesty + UI/Shell | P0 | COMPLETE |
| **X1** | Org & catalog-meta CSV export (`GET /branches/export`, `/departments/export`, `/catalog/*/export`) | P0 | COMPLETE |
| **D1** | Spec / readiness / launch / deploy / security fidelity sync | P1 | COMPLETE |
| **H122x** | Stage 122 exit criteria + freeze ADR | Exit | COMPLETE |

## Explicitly out of this pass

- Paid billing / fabricated MRR / checkout / `subscriptions_live_claimed` Complete (ADR-002)
- User↔Store membership Complete (ADR-005)
- Hard-delete archival Complete (ADR-003)
- Impersonation; POS Hold/Resume; full Billers CRUD; parallel Income; WYSIWYG designer Complete
- PO OCR apply; percentage discount UI polish; year-end tax wizard / multi-book / GDPR DSAR portal Complete
- Reopening Stages 80–121 frozen feature scopes; main `ci.yml` deploy jobs

## O1 acceptance criteria

- [x] `GET /branches?is_active=true|false` (+ `active_only`); same for departments; Company filters; Shell Active/Inactive Branches & Departments.
- [x] Automated proof: `backend/tests/test_stage122_inactive_org_units_o1.py`.

## M1 acceptance criteria

- [x] `GET /catalog/categories|brands|units?is_active=true|false` (+ `active_only`); Inventory catalog filters; Shell Active/Inactive Categories/Brands/Units.
- [x] Automated proof: `backend/tests/test_stage122_inactive_catalog_meta_m1.py`.

## X1 acceptance criteria

- [x] `GET /branches/export`, `/departments/export`, `/catalog/categories/export`, `/catalog/brands/export`, `/catalog/units/export`; Company/Inventory Export buttons.
- [x] Automated proof: `backend/tests/test_stage122_org_catalog_export_x1.py`.

## D1 / H122x acceptance criteria

- [x] `docs/STAGE_122_FIDELITY.md` + exit/freeze ADR-251.
- [x] Automated proof: `test_stage122_fidelity_d1.py`, `test_stage122_exit_h122x.py`.
