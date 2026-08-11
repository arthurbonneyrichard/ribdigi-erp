# Stage 92 Plan — House Console Workflow & Readiness Ops

**Status:** Closed — exit met (H92x); freeze ADR-191  
**Base:** Investigation Export & Evidence Download + Roster Triage & Commercial-Metadata Context + House Regional Formats & Runtime Evidence Detail → House Console Workflow & Readiness Ops  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Open ADR:** [ADR-190](ADR_190_STAGE92_OPEN.md)  
**Exit:** [STAGE_92_EXIT_CRITERIA.md](STAGE_92_EXIT_CRITERIA.md) · freeze [ADR-191](ADR_191_STAGE92_FREEZE.md)  
**Fidelity:** [STAGE_92_FIDELITY.md](STAGE_92_FIDELITY.md)  
**Prior freeze:** [ADR-189](ADR_189_STAGE91_FREEZE.md) · [STAGE_91_EXIT_CRITERIA.md](STAGE_91_EXIT_CRITERIA.md)

## Delivery packs (derived)

```
Investigation Export & Evidence Download Pack
        +
Roster Triage & Commercial-Metadata Context Pack
        +
House Regional Formats & Runtime Evidence Detail Pack
        ↓
House Console Workflow & Readiness Ops
```

## Delivery rules

1. One workstream at a time (full AC + automated tests before the next).
2. Prefer extending audit export, tenant list/export, subscriptions roster, settings, protected health/evidence — do not invent parallel consoles.
3. No demo data / fake MRR. No fabricated email success. No impersonation.
4. After each feature: tests → commit → push → PR update.
5. Do not reopen Stage 1–91 feature scopes. Main `ci.yml` stays deploy-free (**Stage 18 C1**).
6. ADR-002 / ADR-005 remain deferred; ADR-003 stays soft-delete-only (`hard_delete_claimed: false`).

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **B1** | Investigation export + evidence download workflow | P0 | COMPLETE |
| **G1** | Roster triage + commercial-metadata context | P0 | COMPLETE |
| **K1** | House regional formats + runtime evidence detail | P0 | COMPLETE |
| **D1** | Spec / readiness / launch / deploy / security fidelity sync | P1 | COMPLETE |
| **H92x** | Stage 92 exit criteria + freeze ADR | Exit | COMPLETE |

## Explicitly out of this pass

- Paid billing / fabricated MRR / checkout / `subscriptions_live_claimed` Complete (ADR-002)
- User↔Store membership Complete (ADR-005)
- Hard-delete archival Complete (ADR-003)
- Impersonation into customer ERP
- Bulk suspend/activate
- Full House notification center
- Reopening Stages 80–91 frozen feature scopes
- Main `ci.yml` deploy jobs

## B1 acceptance criteria

- [x] Audit export accepts `delivery_only`; Activity export materializes 7d window when dates blank; Health UI downloads `/platform/evidence` JSON.
- [x] Automated proof: `backend/tests/test_stage92_console_workflow_b1.py`.

## G1 acceptance criteria

- [x] Notes search + list last-delivery projection; Active/Trial deep-links; provision plan soft-limit context; billing roster enriched metadata (no MRR).
- [x] Automated proof: `backend/tests/test_stage92_roster_context_g1.py`.

## K1 acceptance criteria

- [x] House `date_format`/`time_format` settings; House timestamp formatting on key surfaces; protected CORS allowlist on health/evidence; database `required` badge.
- [x] Automated proof: `backend/tests/test_stage92_readiness_formats_k1.py`.

## D1 acceptance criteria

- [x] `docs/STAGE_92_FIDELITY.md` maps B1–K1 → readiness / launch / deploy / security.
- [x] Automated proof: `backend/tests/test_stage92_fidelity_d1.py`.

## H92x acceptance criteria

- [x] `docs/STAGE_92_EXIT_CRITERIA.md` + `docs/ADR_191_STAGE92_FREEZE.md`.
- [x] Automated proof: `backend/tests/test_stage92_exit_h92x.py`.
