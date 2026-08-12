# Stage 143 Plan — Tenant MVP Company Profile CSV, Jobs Catalog CSV & Onboarding Checklist CSV Export Fidelity

**Status:** Closed — exit met (H143x); freeze ADR-293  
**Base:** Company Profile CSV + Jobs Catalog CSV + Onboarding Checklist CSV → Tenant MVP Company Profile CSV, Jobs Catalog CSV & Onboarding Checklist CSV Export Fidelity  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Open ADR:** [ADR-292](ADR_292_STAGE143_OPEN.md)  
**Exit:** [STAGE_143_EXIT_CRITERIA.md](STAGE_143_EXIT_CRITERIA.md) · freeze [ADR-293](ADR_293_STAGE143_FREEZE.md)  
**Fidelity:** [STAGE_143_FIDELITY.md](STAGE_143_FIDELITY.md)  
**Prior freeze:** [ADR-291](ADR_291_STAGE142_FREEZE.md) · [STAGE_142_EXIT_CRITERIA.md](STAGE_142_EXIT_CRITERIA.md)

## Delivery packs (derived)

```
Company Profile CSV Pack
        +
Jobs Catalog CSV Pack
        +
Onboarding Checklist CSV Pack
        ↓
Tenant MVP Company Profile CSV, Jobs Catalog CSV & Onboarding Checklist CSV Export Fidelity
```

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **P1** | Company profile CSV + Company `#profile` UI | P0 | COMPLETE |
| **J1** | Jobs catalog CSV + Company `#jobs-catalog` UI | P0 | COMPLETE |
| **O1** | Onboarding checklist CSV + Shell banner UI | P0 | COMPLETE |
| **D1** | Spec / readiness / launch / deploy / security fidelity sync | P1 | COMPLETE |
| **H143x** | Stage 143 exit criteria + freeze ADR | Exit | COMPLETE |

## Explicitly out of this pass

- Paid billing Complete (ADR-002); User↔Store membership (ADR-005); Hard-delete Complete (ADR-003)
- Impersonation; POS Hold/Resume; Billers CRUD; parallel Income; WYSIWYG Complete; PO OCR
- Admin remote-revoke-others; API-key un-revoke; FX soft-`is_active`
- Main `ci.yml` deploy; reopen Stages 1–142
- Stage 128 document/print settings reopen; Stage 140 storage/backup settings reopen
- Celery broker/result URL credentials in jobs CSV; webhook deliveries (runner-up)

## P1 acceptance criteria

- [x] `GET /tenants/me/export`; Company `#profile` Export profile CSV.
- [x] Automated proof: `backend/tests/test_stage143_company_profile_p1.py`.

## J1 acceptance criteria

- [x] `GET /jobs/export`; Company `#jobs-catalog` Export jobs catalog CSV (no broker/result URLs).
- [x] Automated proof: `backend/tests/test_stage143_jobs_catalog_j1.py`.

## O1 acceptance criteria

- [x] `GET /onboarding/checklist/export`; Shell Export checklist CSV.
- [x] Automated proof: `backend/tests/test_stage143_onboarding_checklist_o1.py`.

## D1 / H143x acceptance criteria

- [x] `docs/STAGE_143_FIDELITY.md` + exit/freeze ADR-293.
- [x] Automated proof: `test_stage143_fidelity_d1.py`, `test_stage143_exit_h143x.py`.
