# Stage 128 Plan — Tenant MVP Session Status, Passkey Inventory CSV & Document-Numbering CSV Export Fidelity

**Status:** Closed — exit met (H128x); freeze ADR-263  
**Base:** Session Status Honesty + Passkey Inventory CSV + Document Settings CSV → Tenant MVP Session Status, Passkey Inventory CSV & Document-Numbering CSV Export Fidelity  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Open ADR:** [ADR-262](ADR_262_STAGE128_OPEN.md)  
**Exit:** [STAGE_128_EXIT_CRITERIA.md](STAGE_128_EXIT_CRITERIA.md) · freeze [ADR-263](ADR_263_STAGE128_FREEZE.md)  
**Fidelity:** [STAGE_128_FIDELITY.md](STAGE_128_FIDELITY.md)  
**Prior freeze:** [ADR-261](ADR_261_STAGE127_FREEZE.md) · [STAGE_127_EXIT_CRITERIA.md](STAGE_127_EXIT_CRITERIA.md)

## Delivery packs (derived)

```
Session Status Honesty + CSV Pack
        +
Passkey Inventory CSV Pack
        +
Document Numbering & Print Template Settings CSV Pack
        ↓
Tenant MVP Session Status, Passkey Inventory CSV & Document-Numbering CSV Export Fidelity
```

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **S1** | Session status honesty + secret-free CSV + UI/Shell | P0 | COMPLETE |
| **P1** | Passkey inventory CSV + Security UI | P0 | COMPLETE |
| **N1** | Document numbering / print template settings CSV + Company UI | P0 | COMPLETE |
| **D1** | Spec / readiness / launch / deploy / security fidelity sync | P1 | COMPLETE |
| **H128x** | Stage 128 exit criteria + freeze ADR | Exit | COMPLETE |

## Explicitly out of this pass

- Paid billing Complete (ADR-002); User↔Store membership (ADR-005); Hard-delete Complete (ADR-003)
- Impersonation; POS Hold/Resume; Billers CRUD; parallel Income; WYSIWYG Complete; PO OCR
- API-key un-revoke; FX soft-`is_active`; tenant-wide admin session inventory across users
- Main `ci.yml` deploy; reopen Stages 1–127

## S1 acceptance criteria

- [x] `GET /auth/sessions?status=active|revoked` (+ `active_only`); Security filter; Shell Active/Revoked Sessions; `GET /auth/sessions/export` without refresh-token secrets.
- [x] Automated proof: `backend/tests/test_stage128_session_status_s1.py`.

## P1 acceptance criteria

- [x] `GET /auth/webauthn/credentials/export` without public_key / credential_id; Security Export passkeys CSV button.
- [x] Automated proof: `backend/tests/test_stage128_passkey_export_p1.py`.

## N1 acceptance criteria

- [x] `GET /tenants/me/document-settings/export`; Company Document numbering Export button.
- [x] Automated proof: `backend/tests/test_stage128_document_settings_export_n1.py`.

## D1 / H128x acceptance criteria

- [x] `docs/STAGE_128_FIDELITY.md` + exit/freeze ADR-263.
- [x] Automated proof: `test_stage128_fidelity_d1.py`, `test_stage128_exit_h128x.py`.
