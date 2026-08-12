# Stage 126 Plan — Tenant MVP Inactive Bank Connections, Paused Webhooks & Bank/Webhook CSV Export Fidelity

**Status:** Closed — exit met (H126x); freeze ADR-259  
**Base:** Inactive Bank Connections Honesty + Paused Webhooks Honesty + Bank & Webhook CSV Export → Tenant MVP Inactive Bank Connections, Paused Webhooks & Bank/Webhook CSV Export Fidelity  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Open ADR:** [ADR-258](ADR_258_STAGE126_OPEN.md)  
**Exit:** [STAGE_126_EXIT_CRITERIA.md](STAGE_126_EXIT_CRITERIA.md) · freeze [ADR-259](ADR_259_STAGE126_FREEZE.md)  
**Fidelity:** [STAGE_126_FIDELITY.md](STAGE_126_FIDELITY.md)  
**Prior freeze:** [ADR-257](ADR_257_STAGE125_FREEZE.md) · [STAGE_125_EXIT_CRITERIA.md](STAGE_125_EXIT_CRITERIA.md)

## Delivery packs (derived)

```
Inactive Bank Connections Honesty Pack
        +
Paused Webhooks Honesty Pack
        +
Bank & Webhook CSV Export Pack
        ↓
Tenant MVP Inactive Bank Connections, Paused Webhooks & Bank/Webhook CSV Export Fidelity
```

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **C1** | Inactive bank connections honesty + UI/Shell | P0 | COMPLETE |
| **W1** | Paused webhooks honesty + UI/Shell | P0 | COMPLETE |
| **X1** | Bank & webhook CSV export (`GET /accounting/bank-connections/export`, `/webhooks/export`) | P0 | COMPLETE |
| **D1** | Spec / readiness / launch / deploy / security fidelity sync | P1 | COMPLETE |
| **H126x** | Stage 126 exit criteria + freeze ADR | Exit | COMPLETE |

## Explicitly out of this pass

- Paid billing / fabricated MRR / checkout Complete (ADR-002)
- User↔Store membership Complete (ADR-005); Hard-delete archival Complete (ADR-003)
- Impersonation; POS Hold/Resume; Billers CRUD; parallel Income; WYSIWYG Complete; PO OCR
- API-keys status+export; FX CSV; report-schedule CSV; main `ci.yml` deploy
- Reopening Stages 80–125 frozen feature scopes

## C1 acceptance criteria

- [x] `GET/PATCH /accounting/bank-connections?is_active=` (+ `active_only`); UI filter; Shell Active/Inactive Bank Connections; Deactivate/Reactivate.
- [x] Automated proof: `backend/tests/test_stage126_inactive_bank_connections_c1.py`.

## W1 acceptance criteria

- [x] `GET /webhooks?is_active=true|false` (+ `active_only`); Security filter; Shell Active/Paused Webhooks; Pause/Resume.
- [x] Automated proof: `backend/tests/test_stage126_paused_webhooks_w1.py`.

## X1 acceptance criteria

- [x] `GET /accounting/bank-connections/export`, `/webhooks/export` (no secrets); Export buttons.
- [x] Automated proof: `backend/tests/test_stage126_bank_webhook_export_x1.py`.

## D1 / H126x acceptance criteria

- [x] `docs/STAGE_126_FIDELITY.md` + exit/freeze ADR-259.
- [x] Automated proof: `test_stage126_fidelity_d1.py`, `test_stage126_exit_h126x.py`.
