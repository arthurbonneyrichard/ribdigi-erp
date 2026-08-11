# Grafana / Alertmanager operator examples (Stage 28 A1)

Versioned operator packaging for visualizing Stage 26 M1 Prometheus scrapes and routing MVP alerts. These files are **not** a hosted Grafana / PagerDuty / SIEM deployment.

| File | Role |
|------|------|
| `dashboard-ribdigi-mvp.json.example` | Grafana dashboard over `ribdigi_up` / HTTP rate / latency / 5xx |
| `alertmanager.yml.example` | Alertmanager route + placeholder critical receiver (PagerDuty commented) |

## Local smoke (optional)

```bash
# Prometheus (Stage 26 M1) must scrape /api/v1/metrics first — see ops/prometheus/README.md

# Alertmanager (example only)
docker run --rm -p 9093:9093 \
  -v "$PWD/ops/grafana/alertmanager.yml.example:/etc/alertmanager/alertmanager.yml:ro" \
  prom/alertmanager:v0.27.0 \
  --config.file=/etc/alertmanager/alertmanager.yml

# Grafana: import dashboard-ribdigi-mvp.json.example via UI → Import;
# point datasource at your Prometheus URL. Do not commit fabricated screenshots as pass evidence.
```

Wire Prometheus `alerting.alertmanagers` to Alertmanager when ready (operator). Uncomment PagerDuty in the example only with a real routing key in secrets — never commit keys.

## Deferred

- Hosted Grafana-as-a-service Complete
- Production Alertmanager → PagerDuty wiring Complete
- Centralized SIEM

Authoritative docs: `docs/GRAFANA_PACK_MVP.md`, `docs/OPS_MONITORING_MVP.md` (`test_grafana_pack_a1.py`).
