# Stage 123 Plan — Tenant MVP Inactive Finance Masters, Customer Groups & Finance/Party-Meta CSV Export Fidelity

**Status:** Closed — exit met (H123x); freeze ADR-253  
**Base:** Inactive Finance Masters Honesty + Inactive Customer Groups Honesty + Finance & Party-Meta CSV Export → Tenant MVP Inactive Finance Masters, Customer Groups & Finance/Party-Meta CSV Export Fidelity  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Open ADR:** [ADR-252](ADR_252_STAGE123_OPEN.md)  
**Exit:** [STAGE_123_EXIT_CRITERIA.md](STAGE_123_EXIT_CRITERIA.md) · freeze [ADR-253](ADR_253_STAGE123_FREEZE.md)  
**Fidelity:** [STAGE_123_FIDELITY.md](STAGE_123_FIDELITY.md)  
**Prior freeze:** [ADR-251](ADR_251_STAGE122_FREEZE.md) · [STAGE_122_EXIT_CRITERIA.md](STAGE_122_EXIT_CRITERIA.md)

## Delivery packs (derived)

```
Inactive Finance Masters Honesty Pack
        +
Inactive Customer Groups Honesty Pack
        +
Finance & Party-Meta CSV Export Pack
        ↓
Tenant MVP Inactive Finance Masters, Customer Groups & Finance/Party-Meta CSV Export Fidelity
```

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **F1** | Inactive tax rates / COA / expense categories honesty + UI/Shell | P0 | COMPLETE |
| **G1** | Inactive customer groups honesty + UI/Shell | P0 | COMPLETE |
| **X1** | Finance & party-meta CSV export (`GET /accounting/accounts/export`, `/expenses/categories/export`, `/customers/groups/export`) | P0 | COMPLETE |
| **D1** | Spec / readiness / launch / deploy / security fidelity sync | P1 | COMPLETE |
| **H123x** | Stage 123 exit criteria + freeze ADR | Exit | COMPLETE |

## Explicitly out of this pass

- Paid billing / fabricated MRR / checkout / `subscriptions_live_claimed` Complete (ADR-002)
- User↔Store membership Complete (ADR-005)
- Hard-delete archival Complete (ADR-003)
- Impersonation; POS Hold/Resume; full Billers CRUD; parallel Income; WYSIWYG designer Complete
- PO OCR apply; percentage discount UI polish; year-end tax wizard / multi-book / GDPR DSAR portal Complete
- Reopening Stages 80–122 frozen feature scopes; main `ci.yml` deploy jobs; tax rates CSV reopen (Stage 121)

## F1 acceptance criteria

- [x] `GET /tax/rates?is_active=`, `/accounting/accounts?is_active=`, `/expenses/categories?is_active=` (+ `active_only`); UI filters; Shell Active/Inactive leaves.
- [x] Automated proof: `backend/tests/test_stage123_inactive_finance_masters_f1.py`.

## G1 acceptance criteria

- [x] `GET /customers/groups?is_active=true|false` (+ `active_only`); Sales groups filter; Shell Inactive Customer Groups.
- [x] Automated proof: `backend/tests/test_stage123_inactive_customer_groups_g1.py`.

## X1 acceptance criteria

- [x] `GET /accounting/accounts/export`, `/expenses/categories/export`, `/customers/groups/export`; Export buttons.
- [x] Automated proof: `backend/tests/test_stage123_finance_party_meta_export_x1.py`.

## D1 / H123x acceptance criteria

- [x] `docs/STAGE_123_FIDELITY.md` + exit/freeze ADR-253.
- [x] Automated proof: `test_stage123_fidelity_d1.py`, `test_stage123_exit_h123x.py`.
