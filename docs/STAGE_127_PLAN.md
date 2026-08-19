# Stage 127 Plan — Tenant MVP API-Key Status, FX Rates CSV & Report-Schedule CSV Export Fidelity

**Status:** Closed — exit met (H127x); freeze ADR-261  
**Base:** API-Key Status Honesty + FX Rates CSV + Report-Schedule Enabled Filter & CSV → Tenant MVP API-Key Status, FX Rates CSV & Report-Schedule CSV Export Fidelity  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Open ADR:** [ADR-260](ADR_260_STAGE127_OPEN.md)  
**Exit:** [STAGE_127_EXIT_CRITERIA.md](STAGE_127_EXIT_CRITERIA.md) · freeze [ADR-261](ADR_261_STAGE127_FREEZE.md)  
**Fidelity:** [STAGE_127_FIDELITY.md](STAGE_127_FIDELITY.md)  
**Prior freeze:** [ADR-259](ADR_259_STAGE126_FREEZE.md) · [STAGE_126_EXIT_CRITERIA.md](STAGE_126_EXIT_CRITERIA.md)

## Delivery packs (derived)

```
API-Key Status Honesty + CSV Pack
        +
FX Rates CSV Pack
        +
Report-Schedule Enabled Filter & CSV Pack
        ↓
Tenant MVP API-Key Status, FX Rates CSV & Report-Schedule CSV Export Fidelity
```

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **K1** | API-key status honesty + secret-free CSV + UI/Shell | P0 | COMPLETE |
| **F1** | FX rates CSV export + Credit UI | P0 | COMPLETE |
| **S1** | Report-schedule enabled server filter + CSV + UI | P0 | COMPLETE |
| **D1** | Spec / readiness / launch / deploy / security fidelity sync | P1 | COMPLETE |
| **H127x** | Stage 127 exit criteria + freeze ADR | Exit | COMPLETE |

## Explicitly out of this pass

- Paid billing Complete (ADR-002); User↔Store membership (ADR-005); Hard-delete Complete (ADR-003)
- Impersonation; POS Hold/Resume; Billers CRUD; parallel Income; WYSIWYG Complete; PO OCR
- API-key un-revoke / secret re-reveal; FX soft-`is_active` / replace hard-delete
- Main `ci.yml` deploy; reopen Stages 1–126

## K1 acceptance criteria

- [x] `GET /api-keys?status=active|revoked|expired` (+ `active_only`); Security filter; Shell Active/Revoked/Expired API Keys; `GET /api-keys/export` without secrets.
- [x] Automated proof: `backend/tests/test_stage127_api_key_status_k1.py`.

## F1 acceptance criteria

- [x] `GET /credit/exchange-rates/export`; Credit Export FX rates CSV button.
- [x] Automated proof: `backend/tests/test_stage127_fx_rates_export_f1.py`.

## S1 acceptance criteria

- [x] `GET /reports/schedules?enabled=` + `GET /reports/schedules/export`; Export schedules CSV button.
- [x] Automated proof: `backend/tests/test_stage127_report_schedules_s1.py`.

## D1 / H127x acceptance criteria

- [x] `docs/STAGE_127_FIDELITY.md` + exit/freeze ADR-261.
- [x] Automated proof: `test_stage127_fidelity_d1.py`, `test_stage127_exit_h127x.py`.
