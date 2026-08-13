# Stage 161 Plan — Tenant MVP Reports Profit-Loss Path CSV, Reports Trial-Balance Path CSV & Reports Tax Path CSV Export Fidelity

**Status:** Closed — exit met (H161x); freeze ADR-329  
**Base:** Reports Profit-Loss Path CSV + Reports Trial-Balance Path CSV + Reports Tax Path CSV → Tenant MVP Reports Profit-Loss Path CSV, Reports Trial-Balance Path CSV & Reports Tax Path CSV Export Fidelity  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Open ADR:** [ADR-328](ADR_328_STAGE161_OPEN.md)  
**Exit:** [STAGE_161_EXIT_CRITERIA.md](STAGE_161_EXIT_CRITERIA.md) · freeze [ADR-329](ADR_329_STAGE161_FREEZE.md)  
**Fidelity:** [STAGE_161_FIDELITY.md](STAGE_161_FIDELITY.md)  
**Prior freeze:** [ADR-327](ADR_327_STAGE160_FREEZE.md) · [STAGE_160_EXIT_CRITERIA.md](STAGE_160_EXIT_CRITERIA.md)

## Delivery packs (derived)

```
Reports Profit-Loss Path CSV Pack
        +
Reports Trial-Balance Path CSV Pack
        +
Reports Tax Path CSV Pack
        ↓
Tenant MVP Reports Profit-Loss Path CSV, Reports Trial-Balance Path CSV & Reports Tax Path CSV Export Fidelity
```

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **L1** | Reports profit-loss path CSV + Reports UI | P0 | COMPLETE |
| **B1** | Reports trial-balance path CSV + Reports UI | P0 | COMPLETE |
| **X1** | Reports tax path CSV + Reports/Tax UI | P0 | COMPLETE |
| **D1** | Spec / readiness / launch / deploy / security fidelity sync | P1 | COMPLETE |
| **H161x** | Stage 161 exit criteria + freeze ADR | Exit | COMPLETE |

## Explicitly out of this pass

- Paid billing Complete (ADR-002); User↔Store membership (ADR-005); Hard-delete Complete (ADR-003)
- Fabricated MRR; live subscriptions; checkout Complete
- Impersonation; POS Hold/Resume; Billers CRUD; parallel Income; WYSIWYG Complete; PO OCR
- Admin remote-revoke-others; API-key un-revoke; FX soft-`is_active`
- Main `ci.yml` deploy; reopen Stages 1–160
- External LLM Complete; Stage 153–160 reopen
- Generic `/reports/export` reopen; tax filing path CSV (deferred)

## L1 acceptance criteria

- [x] `GET /reports/profit-loss/export`; Reports Export profit-loss path CSV.
- [x] Automated proof: `backend/tests/test_stage161_profit_loss_l1.py`.

## B1 acceptance criteria

- [x] `GET /reports/trial-balance/export`; Reports Export trial-balance path CSV.
- [x] Automated proof: `backend/tests/test_stage161_trial_balance_b1.py`.

## X1 acceptance criteria

- [x] `GET /reports/tax/export`; Reports/Tax Export tax path CSV.
- [x] Automated proof: `backend/tests/test_stage161_tax_x1.py`.

## D1 / H161x acceptance criteria

- [x] `docs/STAGE_161_FIDELITY.md` + exit/freeze ADR-329.
- [x] Automated proof: `test_stage161_fidelity_d1.py`, `test_stage161_exit_h161x.py`.
