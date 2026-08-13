# ADR-340: Stage 167 Open — Offline Complete E2E Hardening Fidelity

**Status:** Accepted  
**Date:** 2026-08-13  
**Related:** [ADR-339](ADR_339_STAGE166_FREEZE.md), [CHANGE_IMPACT_MVP_UPDATE_2026-08-13.md](CHANGE_IMPACT_MVP_UPDATE_2026-08-13.md), [STAGE_167_PLAN.md](STAGE_167_PLAN.md)

## Context

Stage 166 froze offline catalog cache, accept_client safe re-apply, and Hold soft reserve (ADR-339). The approved runner-up outline adds catalog TTL/refresh policy, conflict re-apply UX polish, and Hold reserve expiry/cleanup — without claiming Offline Complete.

## Decision

Open **Stage 167 — Offline Complete E2E Hardening Fidelity** with packs:

| Pack | Scope |
|------|--------|
| **T1** | Offline catalog TTL (4h default) + freshness helpers + POS refresh policy; pull `recommended_ttl_seconds` |
| **U1** | Conflict re-apply UX polish — conflict `summary` (reason, client keys, accept_client policy) + Settings detail |
| **E1** | Hold soft-reserve expiry — `expires_at` (Alembic `20260813_0095`), auto-expire on list, `POST /pos/holds/expire-stale` |
| **D1 / H167x** | Fidelity cite sync + Stage 167 exit; freeze as **ADR-341** |

## Consequences

- Does **not** claim Offline Complete (E2E browser offline Completes remain deferred).
- Honesty flags stay false.
- Stages 1–166 feature scopes remain frozen.
