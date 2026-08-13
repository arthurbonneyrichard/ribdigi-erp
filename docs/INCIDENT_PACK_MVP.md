# Incident Response Pack MVP — Operator On-Call Packaging

**Status:** Complete (MVP) — Stage 30 I1  
**Evidence:** `backend/tests/test_incident_pack_i1.py` · `/opt/cursor/artifacts/monitoring/stage30_i1_incident_pack.json`  
**Checklist map:** `ops/incident/incident-checklist.json`  
**Runbook example:** `ops/incident/oncall-runbook.md.example`  
**Related:** [OPS_MONITORING_MVP.md](OPS_MONITORING_MVP.md) · [GRAFANA_PACK_MVP.md](GRAFANA_PACK_MVP.md) · `docs/SECURITY_GUIDE.md` §15 · `ops/grafana/alertmanager.yml.example`

This is the **MVP incident response / on-call packaging surface**: severity checklist + operator runbook example extending Stage 26 M1 alerts and Stage 28 A1 Alertmanager. It is **not** hosted PagerDuty SaaS Complete and does **not** claim a live on-call rota already pages production.

## Classification

| Class | Meaning |
|-------|---------|
| `operator_required` | Staff rota, wire Alertmanager receivers, rehearse P1/P2 playbook, retain post-incident notes |
| `ci_proven` | Prometheus/Alertmanager packaging + this pack honesty |
| `deferred` | Hosted PagerDuty Complete; live paging stack; SIEM incident bus |

## Severity map (summary)

| Level | Target ack | Trigger examples (ops) |
|-------|------------|------------------------|
| P1 Critical | 15 min | `RibdigiDown`, active breach, data exfiltration |
| P2 High | 1 hour | Sustained 5xx / not-ready, credential leak |
| P3 Medium | 24 hours | Misconfig, expired cert (TLS Remaining), policy violation |
| P4 Low | 7 days | Hardening follow-ups |

Aligns with `docs/SECURITY_GUIDE.md` §15.1; Alertmanager `severity=critical` routes to `critical-ops` (PagerDuty commented until secrets exist).

## Automation hooks

1. Maintain `ops/incident/incident-checklist.json` (synced by `test_incident_pack_i1.py`).
2. Keep Alertmanager PagerDuty receiver commented in `ops/grafana/alertmanager.yml.example` until a real routing key exists.
3. CI proves packaging honesty only: `pagerduty_hosted_claimed: false`, `oncall_rota_live: false`, `incident_drill_executed: false`.

## Explicitly not claimed

- Hosted PagerDuty / Opsgenie SaaS Complete
- Fabricated paging success or on-call ack SLAs from CI
- Centralized SIEM incident bus Complete
- Treating Stage 28 A1 / Stage 30 I1 Complete as “on-call is live”

## Stage 170 V1 amendment

Tenant/offline/sync severity examples: [INCIDENT_SEVERITY_MATRIX_MVP.md](INCIDENT_SEVERITY_MATRIX_MVP.md) (`ops/mvp/incident-severity-matrix.json`, `test_stage170_severity_v1.py`). PagerDuty / on-call live remain not claimed.

## Sign-off

Stage 30 I1 is met when this doc + checklist + runbook example + evidence JSON exist, `test_incident_pack_i1.py` passes, and SECURITY_GUIDE / DEPLOYMENT_GUIDE / launch / roadmap cite Stage 30 I1 without inventing hosted paging success.
