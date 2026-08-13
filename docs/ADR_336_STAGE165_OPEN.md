# ADR-336: Stage 165 Open — Tenant MVP Offline Client Queue + Hold/Resume + Conflict Resolve Fidelity

**Status:** Accepted  
**Date:** 2026-08-13  
**Related:** [ADR-335](ADR_335_STAGE164_FREEZE.md), [CHANGE_IMPACT_MVP_UPDATE_2026-08-13.md](CHANGE_IMPACT_MVP_UPDATE_2026-08-13.md), [STAGE_165_PLAN.md](STAGE_165_PLAN.md)

## Context

Stage 164 froze sync queue APIs + idempotent POS (ADR-335). The runner-up outline requires an IndexedDB client queue, Partial Hold/Resume, and conflict resolve UX — without claiming Offline Complete or inventing stock reservations.

## Decision

Open **Stage 165 — Tenant MVP Offline Client Queue + Hold/Resume + Conflict Resolve Fidelity** with packs:

| Pack | Scope |
|------|--------|
| **K1** | IndexedDB offline op queue (`frontend/lib/offlineQueue.ts`); enqueue/list/flush via `/sync/push`; bind device in Settings |
| **H1** | POS Hold/Resume Partial — `pos_held_carts` park/resume/discard; **no stock reservation** |
| **R1** | `POST /sync/conflicts/{id}/resolve` + Settings resolve UI (keep_server / dismiss; no silent re-apply) |
| **D1 / H165x** | Fidelity cite sync + Stage 165 exit; freeze as **ADR-337** |

## Consequences

- Does **not** claim Offline Complete or full offline Hold with stock holds.
- Honesty flags stay false.
