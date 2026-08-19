# Stage 164 Plan — Tenant MVP Sync Queue + Idempotent Offline POS Fidelity

**Status:** Closed — exit met (H164x); freeze ADR-335  
**Base:** Real sync queue + push/pull/ack/conflicts + idempotent offline POS  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Open ADR:** [ADR-334](ADR_334_STAGE164_OPEN.md)  
**Exit:** [STAGE_164_EXIT_CRITERIA.md](STAGE_164_EXIT_CRITERIA.md) · freeze [ADR-335](ADR_335_STAGE164_FREEZE.md)  
**Fidelity:** [STAGE_164_FIDELITY.md](STAGE_164_FIDELITY.md)  
**Impact audit:** [CHANGE_IMPACT_MVP_UPDATE_2026-08-13.md](CHANGE_IMPACT_MVP_UPDATE_2026-08-13.md)  
**Prior freeze:** [ADR-333](ADR_333_STAGE163_FREEZE.md)

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **Q1** | Queue schema + real `/sync/status` | P0 | COMPLETE |
| **P1** | `POST /sync/push` | P0 | COMPLETE |
| **L1** | `POST /sync/pull` | P0 | COMPLETE |
| **A1** | `POST /sync/ack` | P0 | COMPLETE |
| **C1** | `GET /sync/conflicts` | P0 | COMPLETE |
| **I1** | Idempotent offline/online POS (`client_request_id`) | P0 | COMPLETE |
| **D1** | Spec / readiness / launch / deploy / security fidelity sync | P1 | COMPLETE |
| **H164x** | Stage 164 exit criteria + freeze ADR | Exit | COMPLETE |

## Explicitly out of this pass

- Claiming Offline Complete end-to-end (PWA offline UI queue + conflict resolve UX + Hold/Resume)
- POS Hold/Resume as Complete; Billers CRUD; parallel Income; WYSIWYG
- ADR-002 / ADR-003 / ADR-005 Completes; fabricated MRR
- Impersonation; hard-delete Complete; main `ci.yml` deploy
- Reopen Stages 1–163 feature scopes (except Stage 163 S1 status supersession)
- Caching `/api/v1/*` or tokens in the service worker

## Acceptance

- [x] Queue tables + real status counts; never invent applied sales.
- [x] Push/pull/ack/conflicts APIs tenant + active-device scoped.
- [x] Duplicate `client_op_id` / `client_request_id` replays safely; payload mismatch → conflict.
- [x] Automated proof: `test_stage164_queue_q1.py`, `test_stage164_push_p1.py`, `test_stage164_pull_l1.py`, `test_stage164_ack_a1.py`, `test_stage164_conflicts_c1.py`, `test_stage164_idempotent_pos_i1.py`.
