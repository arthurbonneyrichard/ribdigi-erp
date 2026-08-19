# Stage 86 Plan — House Provision & Platform Access Ops

**Status:** Closed — exit met (H86x); freeze ADR-179  
**Base:** House Tenant Provision + Platform Email Password Reset + Platform Audit Activity Depth → House Provision & Platform Access Ops  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Open ADR (historical):** [ADR-178](ADR_178_STAGE86_OPEN.md)  
**Exit:** [STAGE_86_EXIT_CRITERIA.md](STAGE_86_EXIT_CRITERIA.md) · [ADR-179](ADR_179_STAGE86_FREEZE.md)  
**Prior freeze:** [ADR-177](ADR_177_STAGE85_FREEZE.md) · [STAGE_85_EXIT_CRITERIA.md](STAGE_85_EXIT_CRITERIA.md)

## Delivery packs (derived)

```
House Tenant Provision Pack
        +
Platform Email Password Reset Pack
        +
Platform Audit Activity Depth Pack
        ↓
House Provision & Platform Access Ops
```

## Delivery rules

1. One workstream at a time (full AC + automated tests before the next).
2. Prefer extending `platform_api` / public `create_tenant` / Stage 85 email-reset / Stage 82 Activity alias — do not invent parallel consoles.
3. No demo data / fake MRR.
4. After each feature: tests → commit → push → PR update.
5. Do not reopen Stage 1–85 feature scopes. Main `ci.yml` stays deploy-free (**Stage 18 C1**).
6. ADR-002 / ADR-005 remain deferred.

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **P1** | House tenant provision (`POST /platform/tenants` + UI) | P0 | COMPLETE |
| **E1** | Platform email password reset | P0 | COMPLETE |
| **A1** | Platform audit filters + Activity alias | P0 | COMPLETE |
| **D1** | Spec / readiness / launch / deploy / security fidelity sync | P1 | COMPLETE |
| **H86x** | Stage 86 exit criteria + freeze ADR | Exit | COMPLETE |

## Explicitly out of this pass

- Paid billing / fabricated MRR / checkout / `subscriptions_live_claimed` Complete (ADR-002)
- User↔Store membership table Complete (ADR-005)
- Reopening Stages 80–85 frozen feature scopes
- Per-user module grant/deny API
- Main `ci.yml` deploy jobs

## P1 acceptance criteria

- [x] `POST /api/v1/platform/tenants` provisions a customer tenant (wraps proven seed path); audited.
- [x] Platform Tenants UI create form; public `/register` remains.
- [x] Automated proof: `backend/tests/test_platform_tenant_provision_p1.py`.

## E1 acceptance criteria

- [x] `POST /api/v1/platform/users/{id}/password-reset-email` + Platform Users UI action.
- [x] Reuses one-time token + emailer; audited.
- [x] Automated proof: `backend/tests/test_platform_email_reset_e1.py`.

## A1 acceptance criteria

- [x] `GET /platform/audit` accepts module/action filters; `/platform/activity` alias; PlatformShell Activity nav.
- [x] Automated proof: `backend/tests/test_platform_audit_activity_a1.py`.

## D1 acceptance criteria

- [x] `docs/STAGE_86_FIDELITY.md` maps P1–A1 → readiness / launch / deploy / security.
- [x] Automated proof: `backend/tests/test_stage86_fidelity_d1.py`.

## H86x acceptance criteria

- [x] `docs/STAGE_86_EXIT_CRITERIA.md` + `docs/ADR_179_STAGE86_FREEZE.md`.
- [x] Automated proof: `backend/tests/test_stage86_exit_h86x.py`.
