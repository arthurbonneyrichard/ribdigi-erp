# ADR-334: Stage 164 Open — Tenant MVP Sync Queue + Idempotent Offline POS Fidelity

**Status:** Accepted  
**Date:** 2026-08-13  
**Related:** [ADR-333](ADR_333_STAGE163_FREEZE.md), [CHANGE_IMPACT_MVP_UPDATE_2026-08-13.md](CHANGE_IMPACT_MVP_UPDATE_2026-08-13.md), [STAGE_164_PLAN.md](STAGE_164_PLAN.md)

## Context

Stage 163 froze Offline foundation (ADR-333): PWA, connectivity, devices, deferred `/sync/status`. The runner-up outline requires a real sync queue, push/pull/ack/conflicts, and an idempotent offline POS path — without fabricating success or claiming Offline Complete.

## Decision

Open **Stage 164 — Tenant MVP Sync Queue + Idempotent Offline POS Fidelity** with packs:

| Pack | Scope |
|------|--------|
| **Q1** | `sync_queue_items` + `sync_conflicts` + Alembic `0092`; `/sync/status` real counts (`sync_enabled: true`) |
| **P1** | `POST /sync/push` — device-scoped ops; idempotent `client_op_id` |
| **L1** | `POST /sync/pull` — pending pull ops + bounded catalog snapshot |
| **A1** | `POST /sync/ack` — acknowledge delivered ops |
| **C1** | `GET /sync/conflicts` — list open conflicts (no silent overwrite) |
| **I1** | `client_request_id` on POS sales + unique `(tenant_id, client_request_id)`; push `pos_sale` reuses online integrity |
| **D1 / H164x** | Fidelity cite sync + Stage 164 exit; freeze as **ADR-335** |

## Consequences

- Does **not** claim Offline Complete, Hold/Resume Complete, or fabricate MRR/billing Completes.
- Stage 163 S1 deferred-only status is superseded for `/sync/status` (test amendment allowed).
- Honesty flags stay false.
