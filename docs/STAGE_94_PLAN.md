# Stage 94 Plan — House Discovery & Runtime Assurance Ops

**Status:** Closed — exit met (H94x); freeze ADR-195  
**Base:** Platform Staff Discovery + Configuration Integrity & Release Identity + Console State & Queue Awareness → House Discovery & Runtime Assurance Ops  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Open ADR:** [ADR-194](ADR_194_STAGE94_OPEN.md)  
**Exit:** [STAGE_94_EXIT_CRITERIA.md](STAGE_94_EXIT_CRITERIA.md) · freeze [ADR-195](ADR_195_STAGE94_FREEZE.md)  
**Fidelity:** [STAGE_94_FIDELITY.md](STAGE_94_FIDELITY.md)  
**Prior freeze:** [ADR-193](ADR_193_STAGE93_FREEZE.md) · [STAGE_93_EXIT_CRITERIA.md](STAGE_93_EXIT_CRITERIA.md)

## Delivery packs (derived)

```
Platform Staff Discovery Pack
        +
Configuration Integrity & Release Identity Pack
        +
Console State & Queue Awareness Pack
        ↓
House Discovery & Runtime Assurance Ops
```

## Delivery rules

1. One workstream at a time (full AC + automated tests before the next).
2. Prefer extending platform users list, settings validation, health/evidence, PlatformShell — do not invent parallel consoles.
3. No demo data / fake MRR. No fabricated email success. No impersonation.
4. After each feature: tests → commit → push → PR update.
5. Do not reopen Stage 1–93 feature scopes. Main `ci.yml` stays deploy-free (**Stage 18 C1**).
6. ADR-002 / ADR-005 remain deferred; ADR-003 stays soft-delete-only (`hard_delete_claimed: false`).

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **W1** | Platform staff discovery | P0 | COMPLETE |
| **H1** | Configuration integrity & release identity | P0 | COMPLETE |
| **T2** | Console state & queue awareness | P0 | COMPLETE |
| **D1** | Spec / readiness / launch / deploy / security fidelity sync | P1 | COMPLETE |
| **H94x** | Stage 94 exit criteria + freeze ADR | Exit | COMPLETE |

## Explicitly out of this pass

- Paid billing / fabricated MRR / checkout / `subscriptions_live_claimed` Complete (ADR-002)
- User↔Store membership Complete (ADR-005)
- Hard-delete archival Complete (ADR-003)
- Impersonation into customer ERP
- Bulk suspend/activate
- Full House notification center
- Reopening Stages 80–93 frozen feature scopes
- Main `ci.yml` deploy jobs

## W1 acceptance criteria

- [x] `GET /platform/users` accepts `q`/`role`/`is_active`; Users UI filters + URL sync; Dashboard Platform-users deep-link.
- [x] Automated proof: `backend/tests/test_stage94_staff_discovery_w1.py`.

## H1 acceptance criteria

- [x] Support email + IANA timezone validation; protected `runtime_identity` (version/build/env) on health/evidence; UI surfaces validation/identity.
- [x] Automated proof: `backend/tests/test_stage94_configuration_integrity_h1.py`.

## T2 acceptance criteria

- [x] PlatformShell at-risk badge; Activity vs Audit empty states; Dashboard plan-distribution link to Plans.
- [x] Automated proof: `backend/tests/test_stage94_console_state_t2.py`.

## D1 acceptance criteria

- [x] `docs/STAGE_94_FIDELITY.md` maps W1–T2 → readiness / launch / deploy / security.
- [x] Automated proof: `backend/tests/test_stage94_fidelity_d1.py`.

## H94x acceptance criteria

- [x] `docs/STAGE_94_EXIT_CRITERIA.md` + `docs/ADR_195_STAGE94_FREEZE.md`.
- [x] Automated proof: `backend/tests/test_stage94_exit_h94x.py`.
