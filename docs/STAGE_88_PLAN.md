# Stage 88 Plan — House Lifecycle & Staff Security Ops

**Status:** Closed — exit met (H88x); freeze ADR-183  
**Base:** Tenant Lifecycle Controls + Tenant Roster Export & At-Risk Queue + Platform Staff Invite & Session Ops → House Lifecycle & Staff Security Ops  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Open ADR (historical):** [ADR-182](ADR_182_STAGE88_OPEN.md)  
**Exit:** [STAGE_88_EXIT_CRITERIA.md](STAGE_88_EXIT_CRITERIA.md) · freeze [ADR-183](ADR_183_STAGE88_FREEZE.md)  
**Fidelity:** [STAGE_88_FIDELITY.md](STAGE_88_FIDELITY.md)  
**Prior freeze:** [ADR-181](ADR_181_STAGE87_FREEZE.md) · [STAGE_87_EXIT_CRITERIA.md](STAGE_87_EXIT_CRITERIA.md)

## Delivery packs (derived)

```
Tenant Lifecycle Controls Pack
        +
Tenant Roster Export & At-Risk Queue Pack
        +
Platform Staff Invite & Session Ops Pack
        ↓
House Lifecycle & Staff Security Ops
```

## Delivery rules

1. One workstream at a time (full AC + automated tests before the next).
2. Prefer extending trial/grace, suspend/activate, Stage 87 export, Stage 86 email tokens / AuthSession revoke — do not invent parallel consoles.
3. No demo data / fake MRR. Activate ≠ paid billing Complete.
4. After each feature: tests → commit → push → PR update.
5. Do not reopen Stage 1–87 feature scopes. Main `ci.yml` stays deploy-free (**Stage 18 C1**).
6. ADR-002 / ADR-005 remain deferred; ADR-003 stays soft-delete-only (`hard_delete_claimed: false`).

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **L1** | Tenant lifecycle controls (trial extend, suspend reason, dates UI) | P0 | COMPLETE |
| **R1** | Tenant roster export + at-risk queue | P0 | COMPLETE |
| **S1** | Platform staff invite-by-email + session ops | P0 | COMPLETE |
| **D1** | Spec / readiness / launch / deploy / security fidelity sync | P1 | COMPLETE |
| **H88x** | Stage 88 exit criteria + freeze ADR | Exit | COMPLETE |

## Explicitly out of this pass

- Paid billing / fabricated MRR / checkout / `subscriptions_live_claimed` Complete (ADR-002)
- User↔Store membership Complete (ADR-005)
- Hard-delete archival Complete (ADR-003)
- Impersonation into customer ERP
- Reopening Stages 80–87 frozen feature scopes
- Main `ci.yml` deploy jobs

## L1 acceptance criteria

- [x] `PATCH /platform/tenants/{id}/lifecycle` extends trial; suspend accepts optional `reason`; detail UI shows trial/grace/days + lifecycle controls.
- [x] Automated proof: `backend/tests/test_platform_tenant_lifecycle_l1.py`.

## R1 acceptance criteria

- [x] `GET /platform/tenants/export` (csv/pdf) and `GET /platform/tenants/at-risk`; Tenants UI export + at-risk list.
- [x] Automated proof: `backend/tests/test_platform_tenant_roster_r1.py`.

## S1 acceptance criteria

- [x] Platform user create/invite without operator-chosen temp password (email set-password token); `GET/DELETE /platform/users/sessions` for platform staff; Users UI.
- [x] Automated proof: `backend/tests/test_platform_staff_security_s1.py`.

## D1 acceptance criteria

- [x] `docs/STAGE_88_FIDELITY.md` maps L1–S1 → readiness / launch / deploy / security.
- [x] Automated proof: `backend/tests/test_stage88_fidelity_d1.py`.

## H88x acceptance criteria

- [x] `docs/STAGE_88_EXIT_CRITERIA.md` + `docs/ADR_183_STAGE88_FREEZE.md`.
- [x] Automated proof: `backend/tests/test_stage88_exit_h88x.py`.
