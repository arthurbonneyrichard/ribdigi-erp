# Service Credit / Warranty MVP — Remedy Honesty Packaging

**Status:** Complete (MVP) — Stage 46 W1  
**Evidence:** `backend/tests/test_service_credit_warranty_w1.py` · `/opt/cursor/artifacts/launch/stage46_w1_service_credit_warranty.json`  
**Register:** `ops/mvp/service-credit-warranty.json`  
**Related:** [SUPPORT_SLA_BOUNDARY_MVP.md](SUPPORT_SLA_BOUNDARY_MVP.md) · [STATUS_UPTIME_MVP.md](STATUS_UPTIME_MVP.md) · [RTO_RPO_MVP.md](RTO_RPO_MVP.md) · [INCIDENT_PACK_MVP.md](INCIDENT_PACK_MVP.md) · [LIABILITY_INDEMNITY_MVP.md](LIABILITY_INDEMNITY_MVP.md) · [MSA_ADDENDUM_MVP.md](MSA_ADDENDUM_MVP.md) · [CHANGE_GOVERNANCE_MVP.md](CHANGE_GOVERNANCE_MVP.md) · [STAGE_46_PLAN.md](STAGE_46_PLAN.md) · [ADR_097_STAGE46_OPEN.md](ADR_097_STAGE46_OPEN.md)

This is the **MVP Service Credit / Warranty honesty packaging surface**: a customer-facing remedy boundary consolidating Stage 36 support-SLA and Stage 40 uptime / Stage 45 RTO adjacency with Stage 46 L1 liability honesty into a service-credit / warranty Remaining pack. It does **not** claim live service credits Complete, warranty Complete, measured uptime SLA credits Complete, or that credit schedules are already executed in production billing.

## Classification

| Status | Meaning |
|--------|---------|
| `packaged` | Service-credit / warranty step indexed to Complete (MVP) support / availability surfaces |
| `remaining` | Live service credits / warranty / uptime-credit execution still required |

Every step keeps `done: false`. Top-level `service_credits_live: false` / `warranty_live_claimed: false` / `uptime_credit_claimed: false` / `remedy_schedule_live: false`.

## Register scope

1. Stage 36 support SLA severity / ack boundary adjacency (not credit Complete).
2. Stage 40 status / uptime honesty adjacency (not measured 99.9% credits).
3. Stage 45 RTO / RPO objectives adjacency (not measured RTO remedies).
4. Stage 30 / 36 incident escalation adjacency.
5. Stage 46 L1 liability / indemnity adjacency (risk allocation ≠ credits).
6. Stage 39 MSA security addendum commercial adjacency.
7. Stage 41 change / maintenance-window adjacency.
8. PRODUCT_OVERVIEW uptime theme honesty.
9. Live service credits Remaining.
10. Warranty / remedy-schedule Remaining.

## Automation hooks

1. Maintain `ops/mvp/service-credit-warranty.json` (synced by `test_service_credit_warranty_w1.py`).
2. Align honesty with Stage 36 support-SLA / Stage 40 uptime Remaining flags.
3. CI proves packaging honesty only — never forges live service credits or warranty Complete.

## Explicitly not claimed

- Live service credits Complete because Stage 46 W1 packaging exists
- Warranty Complete / warranty portal Complete
- Measured uptime SLA credits Complete
- Billing-integrated remedy schedule Complete
- Live go-live / §7 / attestation Complete
- Re-packaging Stage 36–45 support / uptime / RTO packs as new runtime Complete

## Sign-off

Stage 46 W1 is met when this doc + register JSON + evidence JSON exist, `test_service_credit_warranty_w1.py` passes, and LAUNCH_CHECKLIST / DEVELOPMENT_ROADMAP / plan cite Stage 46 W1 without inventing live service credits / warranty Complete.
