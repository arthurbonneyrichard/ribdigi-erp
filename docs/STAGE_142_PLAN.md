# Stage 142 Plan — Tenant MVP POS Sales Register CSV, Session Z-Report CSV & Store Cash Drawer Settings CSV Export Fidelity

**Status:** Closed — exit met (H142x); freeze ADR-291  
**Base:** POS Sales Register CSV + Session Z-Report CSV + Store Cash Drawer Settings CSV → Tenant MVP POS Sales Register CSV, Session Z-Report CSV & Store Cash Drawer Settings CSV Export Fidelity  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Open ADR:** [ADR-290](ADR_290_STAGE142_OPEN.md)  
**Exit:** [STAGE_142_EXIT_CRITERIA.md](STAGE_142_EXIT_CRITERIA.md) · freeze [ADR-291](ADR_291_STAGE142_FREEZE.md)  
**Fidelity:** [STAGE_142_FIDELITY.md](STAGE_142_FIDELITY.md)  
**Prior freeze:** [ADR-289](ADR_289_STAGE141_FREEZE.md) · [STAGE_141_EXIT_CRITERIA.md](STAGE_141_EXIT_CRITERIA.md)

## Delivery packs (derived)

```
POS Sales Register CSV Pack
        +
Session Z-Report CSV Pack
        +
Store Cash Drawer Settings CSV Pack
        ↓
Tenant MVP POS Sales Register CSV, Session Z-Report CSV & Store Cash Drawer Settings CSV Export Fidelity
```

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **S1** | POS sales register list + CSV + POS UI | P0 | COMPLETE |
| **Z1** | Session Z-report CSV + POS UI | P0 | COMPLETE |
| **C1** | Drawer settings CSV + Stores `#cash-drawer` UI | P0 | COMPLETE |
| **D1** | Spec / readiness / launch / deploy / security fidelity sync | P1 | COMPLETE |
| **H142x** | Stage 142 exit criteria + freeze ADR | Exit | COMPLETE |

## Explicitly out of this pass

- Paid billing Complete (ADR-002); User↔Store membership (ADR-005); Hard-delete Complete (ADR-003)
- Impersonation; POS Hold/Resume; Billers CRUD; parallel Income; WYSIWYG Complete; PO OCR
- Admin remote-revoke-others; API-key un-revoke; FX soft-`is_active`
- Main `ci.yml` deploy; reopen Stages 1–141
- Stage 130 POS sessions inventory reopen
- Kick bytes / ESC-POS payload in drawer settings CSV

## S1 acceptance criteria

- [x] `GET /pos/sales` + `GET /pos/sales/export` (optional session/store/date filters); POS Export sales CSV.
- [x] Automated proof: `backend/tests/test_stage142_pos_sales_s1.py`.

## Z1 acceptance criteria

- [x] `GET /pos/sessions/{id}/report/export`; POS Export Z-report CSV (summary + sale lines).
- [x] Automated proof: `backend/tests/test_stage142_z_report_z1.py`.

## C1 acceptance criteria

- [x] `GET /stores/drawer-settings/export`; Stores `#cash-drawer` Export drawer settings CSV (no kick bytes).
- [x] Automated proof: `backend/tests/test_stage142_drawer_settings_c1.py`.

## D1 / H142x acceptance criteria

- [x] `docs/STAGE_142_FIDELITY.md` + exit/freeze ADR-291.
- [x] Automated proof: `test_stage142_fidelity_d1.py`, `test_stage142_exit_h142x.py`.
