# Grafana / Alertmanager Pack MVP — Operator Observability Packaging

**Status:** Complete (MVP) — Stage 28 A1  
**Evidence:** `backend/tests/test_grafana_pack_a1.py` · `/opt/cursor/artifacts/monitoring/stage28_a1_grafana_pack.json`  
**Assets:** `ops/grafana/dashboard-ribdigi-mvp.json.example` · `ops/grafana/alertmanager.yml.example`  
**Related:** [OPS_MONITORING_MVP.md](OPS_MONITORING_MVP.md) (Stage 26 M1) · `ops/prometheus/`

This is the **MVP Grafana / Alertmanager packaging surface**: example dashboard JSON + Alertmanager config extending Stage 26 M1 Prometheus scrape/alerts. It is **not** hosted Grafana/PagerDuty/SIEM as deployed-by-default SaaS Complete.

## Classification

| Class | Meaning |
|-------|---------|
| `operator_required` | Run Prometheus → import dashboard → start Alertmanager → optionally wire PagerDuty with secrets |
| `ci_proven` | Scrape/alert packaging (Stage 26 M1) + this pack honesty (`test_grafana_pack_a1.py`) |
| `deferred` | Hosted Grafana SaaS; production PagerDuty Complete; SIEM |

## Automation hooks

1. Keep `ops/grafana/*.example` as authoritative templates (synced by `test_grafana_pack_a1.py`).
2. Dashboard panels use live series: `ribdigi_up`, `ribdigi_http_requests_total`, duration sum/count (Stage 5 H5 / Stage 26 M1).
3. Alertmanager example routes `severity=critical` separately; PagerDuty receiver stays commented until a real routing key exists.
4. CI proves packaging honesty only: `hosted_grafana_claimed: false`, `pagerduty_wired: false`.

## Explicitly not claimed

- Hosted Grafana dashboards deployed in production by default
- Green Alertmanager → PagerDuty paging stack
- Centralized SIEM / log analytics Complete
- Treating Stage 26 M1 / Stage 28 A1 Complete as “ops observability SaaS live”

## Sign-off

Stage 28 A1 is met when this doc + Grafana/Alertmanager examples + evidence JSON exist, `test_grafana_pack_a1.py` passes, and PRODUCTION_READINESS / launch / roadmap cite Stage 28 A1 without inventing hosted SaaS success.
