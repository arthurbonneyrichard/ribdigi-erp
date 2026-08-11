# Support SLA Boundary MVP — Customer-Facing SLA / Escalation Honesty Packaging

**Status:** Complete (MVP) — Stage 36 S1  
**Evidence:** `backend/tests/test_support_sla_boundary_s1.py` · `/opt/cursor/artifacts/launch/stage36_s1_support_sla_boundary.json`  
**Register:** `ops/mvp/support-sla-boundary.json`  
**Related:** [SUPPORT_RUNBOOK_MVP.md](SUPPORT_RUNBOOK_MVP.md) · [INCIDENT_PACK_MVP.md](INCIDENT_PACK_MVP.md) · [ASSURANCE_EVIDENCE_MVP.md](ASSURANCE_EVIDENCE_MVP.md) · [STAGE_36_PLAN.md](STAGE_36_PLAN.md) · [STAGE_34_PLAN.md](STAGE_34_PLAN.md)

This is the **MVP support SLA / incident escalation boundary packaging surface**: a customer/procurement-facing honesty boundary consolidating Stage 30 support runbook and incident packs (severity ack targets, escalation path, Alertmanager/PagerDuty Remaining). It completes the Stage 34 deferred S1 scope — it does **not** claim live support SLA Complete, hosted PagerDuty/helpdesk SaaS Complete, or that an on-call rota already pages production.

## Classification

| Status | Meaning |
|--------|---------|
| `packaged` | Boundary step indexed to Complete (MVP) product / packaging surfaces |
| `remaining` | Live SLA / hosted paging / operator drill still required |

Every step keeps `done: false`. Top-level `support_sla_claimed: false` / `pagerduty_hosted_claimed: false` / `oncall_rota_live: false` / `incident_drill_executed: false`.

## Register scope

1. Customer-facing severity → ack-target boundary (P1–P4 packaging).
2. Incident escalation path indexed to Stage 30 I1 checklist.
3. Support runbook / ADMIN_MANUAL ops map linkage.
4. Alertmanager critical routing honesty (PagerDuty commented until secrets).
5. On-call rota Remaining honesty.
6. Customer support contact / handoff boundary.
7. Post-incident notes / evidence ledger linkage.
8. Hosted helpdesk / PagerDuty SaaS deferred Remaining.
9. Live incident drill Remaining.
10. Live support SLA execution Remaining.

## Automation hooks

1. Maintain `ops/mvp/support-sla-boundary.json` (synced by `test_support_sla_boundary_s1.py`).
2. Align honesty with support runbook / incident pack / residual-risk flags.
3. CI proves packaging honesty only — never forges live SLA or PagerDuty Complete.

## Explicitly not claimed

- Live support SLA / status-page Complete because Stage 36 S1 packaging exists
- Hosted PagerDuty / Opsgenie / helpdesk SaaS Complete
- Live on-call rota paging production Complete
- Live incident drill executed Complete
- Live go-live / §7 / attestation Complete
- Re-packaging Stage 30 support / incident packs as new runtime Complete

## Sign-off

Stage 36 S1 is met when this doc + register JSON + evidence JSON exist, `test_support_sla_boundary_s1.py` passes, and LAUNCH_CHECKLIST / PRODUCTION_READINESS / plan / roadmap cite Stage 36 S1 without inventing live SLA or PagerDuty Complete.
