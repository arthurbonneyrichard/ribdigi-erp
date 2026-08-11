# Stage 91 Plan — House Operator Investigation & Evidence Ops

**Status:** Closed — exit met (H91x); freeze ADR-189  
**Base:** Audit/Activity Date-Range Investigation + Dashboard→Roster Deep-Links & Tenant Delivery Context + Staff Presence / Health Required Badges / House TZ + Operator Evidence Export → House Operator Investigation & Evidence Ops  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Open ADR:** [ADR-188](ADR_188_STAGE91_OPEN.md)  
**Exit:** [STAGE_91_EXIT_CRITERIA.md](STAGE_91_EXIT_CRITERIA.md) · freeze [ADR-189](ADR_189_STAGE91_FREEZE.md)  
**Fidelity:** [STAGE_91_FIDELITY.md](STAGE_91_FIDELITY.md)  
**Prior freeze:** [ADR-187](ADR_187_STAGE90_FREEZE.md) · [STAGE_90_EXIT_CRITERIA.md](STAGE_90_EXIT_CRITERIA.md)

## Delivery packs (derived)

```
Audit/Activity Date-Range Investigation Pack
        +
Dashboard→Roster Deep-Links & Tenant Delivery Context Pack
        +
Staff Presence / Health Required Badges / House TZ + Operator Evidence Export Pack
        ↓
House Operator Investigation & Evidence Ops
```

## Delivery rules

1. One workstream at a time (full AC + automated tests before the next).
2. Prefer extending audit.query_logs, dashboard links, AuthSession, health/security_posture — do not invent parallel consoles.
3. No demo data / fake MRR. No fabricated email success. No impersonation.
4. After each feature: tests → commit → push → PR update.
5. Do not reopen Stage 1–90 feature scopes. Main `ci.yml` stays deploy-free (**Stage 18 C1**).
6. ADR-002 / ADR-005 remain deferred; ADR-003 stays soft-delete-only (`hard_delete_claimed: false`).

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **I1** | Audit/Activity date-range investigation | P0 | COMPLETE |
| **N1** | Dashboard→roster deep-links + tenant last delivery context | P0 | COMPLETE |
| **P1** | Staff presence, health required badges, House TZ, evidence export | P0 | COMPLETE |
| **D1** | Spec / readiness / launch / deploy / security fidelity sync | P1 | COMPLETE |
| **H91x** | Stage 91 exit criteria + freeze ADR | Exit | COMPLETE |

## Explicitly out of this pass

- Paid billing / fabricated MRR / checkout / `subscriptions_live_claimed` Complete (ADR-002)
- User↔Store membership Complete (ADR-005)
- Hard-delete archival Complete (ADR-003)
- Impersonation into customer ERP
- Bulk suspend/activate
- Full House notification center
- Reopening Stages 80–90 frozen feature scopes
- Main `ci.yml` deploy jobs

## I1 acceptance criteria

- [x] `GET /platform/audit` + `/activity` accept `from_date`/`to_date`; Activity defaults to recent 7d window; Audit UI date inputs wired to list + export.
- [x] Automated proof: `backend/tests/test_platform_audit_investigation_i1.py`.

## N1 acceptance criteria

- [x] Dashboard Grace/Suspended/At-risk deep-links; tenants page hydrates `status` from query; tenant detail shows last House email delivery summary.
- [x] Automated proof: `backend/tests/test_platform_nav_delivery_n1.py`.

## P1 acceptance criteria

- [x] Platform users `last_session_at` + `active_session_count`; Health required badges; Settings House timezone; `GET /platform/evidence` operator evidence pack (honesty flags false).
- [x] Automated proof: `backend/tests/test_house_posture_evidence_p1.py`.

## D1 acceptance criteria

- [x] `docs/STAGE_91_FIDELITY.md` maps I1–P1 → readiness / launch / deploy / security.
- [x] Automated proof: `backend/tests/test_stage91_fidelity_d1.py`.

## H91x acceptance criteria

- [x] `docs/STAGE_91_EXIT_CRITERIA.md` + `docs/ADR_189_STAGE91_FREEZE.md`.
- [x] Automated proof: `backend/tests/test_stage91_exit_h91x.py`.
