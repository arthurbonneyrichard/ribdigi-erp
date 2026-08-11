# Incident response / on-call packaging (Stage 30 I1)

| File | Role |
|------|------|
| `incident-checklist.json` | Severity + operator steps; honesty flags for PagerDuty / rota / drills |
| `oncall-runbook.md.example` | Detection → recovery playbook template |

Authoritative MVP doc: `docs/INCIDENT_PACK_MVP.md` (`backend/tests/test_incident_pack_i1.py`).

Extends Stage 26 M1 Prometheus alerts and Stage 28 A1 Alertmanager. Do **not** treat this packaging as hosted PagerDuty SaaS Complete. Flags stay `pagerduty_hosted_claimed: false`, `oncall_rota_live: false`, `incident_drill_executed: false`.
