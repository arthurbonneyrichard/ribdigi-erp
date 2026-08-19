# Stage 93 Plan — House Navigation & Runtime Ops

**Status:** Closed — exit met (H93x); freeze ADR-193  
**Base:** Roster Navigation & Export + Staff Delivery & Integrity + Format, Evidence & Runtime Posture → House Navigation & Runtime Ops  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Open ADR:** [ADR-192](ADR_192_STAGE93_OPEN.md)  
**Exit:** [STAGE_93_EXIT_CRITERIA.md](STAGE_93_EXIT_CRITERIA.md) · freeze [ADR-193](ADR_193_STAGE93_FREEZE.md)  
**Fidelity:** [STAGE_93_FIDELITY.md](STAGE_93_FIDELITY.md)  
**Prior freeze:** [ADR-191](ADR_191_STAGE92_FREEZE.md) · [STAGE_92_EXIT_CRITERIA.md](STAGE_92_EXIT_CRITERIA.md)

## Delivery packs (derived)

```
Roster Navigation & Export Pack
        +
Staff Delivery & Integrity Pack
        +
Format, Evidence & Runtime Posture Pack
        ↓
House Navigation & Runtime Ops
```

## Delivery rules

1. One workstream at a time (full AC + automated tests before the next).
2. Prefer extending tenant list/export, industry constants, invite delivery audits, settings/formats, protected health/evidence — do not invent parallel consoles.
3. No demo data / fake MRR. No fabricated email success. No impersonation.
4. After each feature: tests → commit → push → PR update.
5. Do not reopen Stage 1–92 feature scopes. Main `ci.yml` stays deploy-free (**Stage 18 C1**).
6. ADR-002 / ADR-005 remain deferred; ADR-003 stays soft-delete-only (`hard_delete_claimed: false`).

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **M1** | Roster navigation & export | P0 | COMPLETE |
| **J1** | Staff delivery & integrity | P0 | COMPLETE |
| **V1** | Format, evidence & runtime posture | P0 | COMPLETE |
| **D1** | Spec / readiness / launch / deploy / security fidelity sync | P1 | COMPLETE |
| **H93x** | Stage 93 exit criteria + freeze ADR | Exit | COMPLETE |


## Explicitly out of this pass

- Paid billing / fabricated MRR / checkout / `subscriptions_live_claimed` Complete (ADR-002)
- User↔Store membership Complete (ADR-005)
- Hard-delete archival Complete (ADR-003)
- Impersonation into customer ERP
- Bulk suspend/activate
- Full House notification center
- Reopening Stages 80–92 frozen feature scopes
- Main `ci.yml` deploy jobs

## M1 acceptance criteria

- [x] Industry catalog endpoint + UI; `created_this_month` filter; URL filter sync; notes 2000 limit; suspended_reason search; at-risk focus styling; PDF last-delivery; billing grace column.
- [x] Automated proof: `backend/tests/test_stage93_roster_navigation_m1.py`.

## J1 acceptance criteria

- [x] Users list last invite delivery; honest invite messaging; audit verify `verified_at` / broken timestamps formatted in UI.
- [x] Automated proof: `backend/tests/test_stage93_staff_integrity_j1.py`.

## V1 acceptance criteria

- [x] House `number_format`; shared evidence download; Health Celery badge + idle timeout + CORS wildcard alert; house_runtime on health/evidence.
- [x] Automated proof: `backend/tests/test_stage93_runtime_posture_v1.py`.

## D1 acceptance criteria

- [x] `docs/STAGE_93_FIDELITY.md` maps M1–V1 → readiness / launch / deploy / security.
- [x] Automated proof: `backend/tests/test_stage93_fidelity_d1.py`.

## H93x acceptance criteria

- [x] `docs/STAGE_93_EXIT_CRITERIA.md` + `docs/ADR_193_STAGE93_FREEZE.md`.
- [x] Automated proof: `backend/tests/test_stage93_exit_h93x.py`.
