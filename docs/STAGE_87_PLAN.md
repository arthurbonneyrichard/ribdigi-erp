# Stage 87 Plan — House Integrity & Console Boundary Ops

**Status:** Closed — exit met (H87x); freeze ADR-181  
**Base:** Platform Audit Export & Chain Verify + House Ops Surface Polish + Console Boundary Hardening → House Integrity & Console Boundary Ops  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Open ADR (historical):** [ADR-180](ADR_180_STAGE87_OPEN.md)  
**Exit:** [STAGE_87_EXIT_CRITERIA.md](STAGE_87_EXIT_CRITERIA.md) · freeze [ADR-181](ADR_181_STAGE87_FREEZE.md)  
**Fidelity:** [STAGE_87_FIDELITY.md](STAGE_87_FIDELITY.md)  
**Prior freeze:** [ADR-179](ADR_179_STAGE86_FREEZE.md) · [STAGE_86_EXIT_CRITERIA.md](STAGE_86_EXIT_CRITERIA.md)

## Delivery packs (derived)

```
Platform Audit Export & Chain Verify Pack
        +
House Ops Surface Polish Pack
        +
Console Boundary Hardening Pack
        ↓
House Integrity & Console Boundary Ops
```

## Delivery rules

1. One workstream at a time (full AC + automated tests before the next).
2. Prefer extending tenant audit export/verify, health payload, Shell principal redirects — do not invent parallel consoles.
3. No demo data / fake MRR.
4. After each feature: tests → commit → push → PR update.
5. Do not reopen Stage 1–86 feature scopes. Main `ci.yml` stays deploy-free (**Stage 18 C1**).
6. ADR-002 / ADR-005 remain deferred; ADR-003 stays soft-delete-only (`hard_delete_claimed: false`).

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **X1** | Platform audit export + chain verify | P0 | COMPLETE |
| **Y1** | House ops surface (health cards, last activity, notes, settings honesty) | P0 | COMPLETE |
| **Z1** | Console boundary hardening + soft-delete honesty | P0 | COMPLETE |
| **D1** | Spec / readiness / launch / deploy / security fidelity sync | P1 | COMPLETE |
| **H87x** | Stage 87 exit criteria + freeze ADR | Exit | COMPLETE |

## Explicitly out of this pass

- Paid billing / fabricated MRR / checkout / `subscriptions_live_claimed` Complete (ADR-002)
- User↔Store membership Complete (ADR-005)
- Hard-delete archival Complete (ADR-003)
- Reopening Stages 80–86 frozen feature scopes
- Main `ci.yml` deploy jobs

## X1 acceptance criteria

- [x] `GET /platform/audit/export` (csv/pdf) and `GET /platform/audit/verify` on platform tenant.
- [x] Platform Audit UI export + verify actions.
- [x] Automated proof: `backend/tests/test_platform_audit_integrity_x1.py`.

## Y1 acceptance criteria

- [x] Health UI shows check cards (database/redis/broker); tenant detail shows `last_activity_at`; operator notes PATCH; settings honesty vs `/company`.
- [x] Automated proof: `backend/tests/test_house_ops_surface_y1.py`.

## Z1 acceptance criteria

- [x] Principal cookie + Next middleware / shared guard; Security uses PlatformShell for platform staff; soft-delete honesty copy on Users UIs.
- [x] Automated proof: `backend/tests/test_console_boundary_z1.py`.

## D1 acceptance criteria

- [x] `docs/STAGE_87_FIDELITY.md` maps X1–Z1 → readiness / launch / deploy / security.
- [x] Automated proof: `backend/tests/test_stage87_fidelity_d1.py`.

## H87x acceptance criteria

- [x] `docs/STAGE_87_EXIT_CRITERIA.md` + `docs/ADR_181_STAGE87_FREEZE.md`.
- [x] Automated proof: `backend/tests/test_stage87_exit_h87x.py`.
