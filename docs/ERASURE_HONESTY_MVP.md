# Erasure Honesty MVP — Soft-Delete / ADR-003 Boundary Packaging

**Status:** Complete (MVP) — Stage 37 E1  
**Evidence:** `backend/tests/test_erasure_honesty_e1.py` · `/opt/cursor/artifacts/launch/stage37_e1_erasure_honesty.json`  
**Register:** `ops/mvp/erasure-honesty.json`  
**Related:** [ADR_003_USER_DELETE_POLICY.md](ADR_003_USER_DELETE_POLICY.md) · [DEFERRED_ADR_REGISTER_MVP.md](DEFERRED_ADR_REGISTER_MVP.md) · [DATA_PORTABILITY_MVP.md](DATA_PORTABILITY_MVP.md) · [POST_MVP_BACKLOG_MVP.md](POST_MVP_BACKLOG_MVP.md) · [STAGE_37_PLAN.md](STAGE_37_PLAN.md) · [ADR_079_STAGE37_OPEN.md](ADR_079_STAGE37_OPEN.md)

This is the **MVP erasure / soft-delete honesty packaging surface**: a customer/procurement-facing boundary indexing ADR-003 soft-delete-only user deactivation (`DELETE /users/{id}` → `is_active=false` + session revoke + `user_deactivated` audit) versus BR-3.1 hard-delete with archival Remaining. It extends Stage 31 R1 deferred ADR register and Stage 37 P1 data-protection packaging — it does **not** claim hard-delete archival Complete, GDPR right-to-erasure certification Complete, anonymize/reassignment workflow Complete, or that permanent row removal already ships.

## Classification

| Status | Meaning |
|--------|---------|
| `packaged` | Erasure honesty step indexed to Complete (MVP) soft-delete / ADR surfaces |
| `remaining` | Hard-delete archival / anonymize / GDPR erasure certification still required |

Every step keeps `done: false`. Top-level `hard_delete_claimed: false` / `erasure_complete_claimed: false` / `anonymize_workflow_claimed: false` / `deferred_implemented_claimed: false`.

## Register scope

1. ADR-003 accepted soft-delete-only decision indexed.
2. `DELETE /users/{id}` deactivate + session revoke honesty.
3. `user_deactivated` audit event honesty.
4. Reactivation via `PATCH /users/{id}` `is_active=true` honesty.
5. No hard-delete API honesty (no row removal endpoint).
6. Self-deactivation forbidden honesty.
7. Deferred ADR register ADR-003 row honesty.
8. Post-MVP backlog hard-delete Remaining.
9. Product / catalog soft-deactivate pattern honesty (not user hard-delete).
10. Hard-delete with archival Remaining (BR-3.1 post-MVP).

## Automation hooks

1. Maintain `ops/mvp/erasure-honesty.json` (synced by `test_erasure_honesty_e1.py`).
2. Align honesty with ADR-003 / deferred-adr-register / API soft-delete docs.
3. CI proves packaging honesty only — never forges hard-delete or GDPR erasure Complete.

## Explicitly not claimed

- Hard-delete with data archival Complete because Stage 37 E1 packaging exists
- GDPR right-to-erasure certification Complete
- Anonymize / reassignment workflow Complete
- Deferred ADR-003 implementation Complete
- Live go-live / §7 / attestation Complete
- Re-packaging Stage 1 / 21 user lifecycle as permanent delete Complete

## Sign-off

Stage 37 E1 is met when this doc + register JSON + evidence JSON exist, `test_erasure_honesty_e1.py` passes, and LAUNCH_CHECKLIST / DEVELOPMENT_ROADMAP / plan cite Stage 37 E1 without inventing hard-delete Complete.

See also Stage 183 hard-delete remaining-gate index: [`HARD_DELETE_REMAINING_GATE_MVP.md`](HARD_DELETE_REMAINING_GATE_MVP.md).
