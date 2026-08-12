# Stage 135 Plan — Tenant MVP Purchase Return CSV, SMS Settings Export & Stores Transfer CSV Fidelity

**Status:** Closed — exit met (H135x); freeze ADR-277  
**Base:** Purchase Return CSV + SMS Settings Export + Stores Transfer CSV → Tenant MVP Purchase Return CSV, SMS Settings Export & Stores Transfer CSV Fidelity  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Open ADR:** [ADR-276](ADR_276_STAGE135_OPEN.md)  
**Exit:** [STAGE_135_EXIT_CRITERIA.md](STAGE_135_EXIT_CRITERIA.md) · freeze [ADR-277](ADR_277_STAGE135_FREEZE.md)  
**Fidelity:** [STAGE_135_FIDELITY.md](STAGE_135_FIDELITY.md)  
**Prior freeze:** [ADR-275](ADR_275_STAGE134_FREEZE.md) · [STAGE_134_EXIT_CRITERIA.md](STAGE_134_EXIT_CRITERIA.md)

## Delivery packs (derived)

```
Purchase Return CSV Pack
        +
SMS Settings Export Pack
        +
Stores Transfer CSV Pack
        ↓
Tenant MVP Purchase Return CSV, SMS Settings Export & Stores Transfer CSV Fidelity
```

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **R1** | Purchase return header CSV honoring status + Purchasing UI | P0 | COMPLETE |
| **S1** | SMS settings CSV secret-free + Company UI | P0 | COMPLETE |
| **T1** | Stores transfer header CSV + status filter + Shell leaves | P0 | COMPLETE |
| **D1** | Spec / readiness / launch / deploy / security fidelity sync | P1 | COMPLETE |
| **H135x** | Stage 135 exit criteria + freeze ADR | Exit | COMPLETE |

## Explicitly out of this pass

- Paid billing Complete (ADR-002); User↔Store membership (ADR-005); Hard-delete Complete (ADR-003)
- Impersonation; POS Hold/Resume; Billers CRUD; parallel Income; WYSIWYG Complete; PO OCR
- Admin remote-revoke-others; API-key un-revoke; FX soft-`is_active`
- Main `ci.yml` deploy; reopen Stages 1–134
- Line dumps; customer/supplier payment tenant list APIs

## R1 acceptance criteria

- [x] `GET /purchasing/returns/export` honoring status; Purchasing Export returns CSV button.
- [x] Automated proof: `backend/tests/test_stage135_returns_export_r1.py`.

## S1 acceptance criteria

- [x] `GET /settings/sms/export` secret-free; Company Export SMS settings CSV button.
- [x] Automated proof: `backend/tests/test_stage135_sms_settings_export_s1.py`.

## T1 acceptance criteria

- [x] `GET /stores/transfers/export` honoring status; Stores filter + Export; Shell status leaves.
- [x] Automated proof: `backend/tests/test_stage135_stores_transfers_t1.py`.

## D1 / H135x acceptance criteria

- [x] `docs/STAGE_135_FIDELITY.md` + exit/freeze ADR-277.
- [x] Automated proof: `test_stage135_fidelity_d1.py`, `test_stage135_exit_h135x.py`.
