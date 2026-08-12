# Prometheus scrape & alerts (Stage 26 M1)

Versioned operator configs for scraping RIBDIGI's existing Prometheus-text endpoint and evaluating MVP alert rules.

| File | Role |
|------|------|
| `prometheus.yml` | Scrape `GET /api/v1/metrics`; optional blackbox job for `GET /api/v1/health/ready` |
| `alerts/ribdigi.yml` | `RibdigiDown`, `RibdigiHighErrorRate`, `RibdigiHighLatency`, `RibdigiNotReady`, optional RabbitMQ depth |

These files are **not** started by CI or default `docker-compose`. They prove scrape/alert fidelity over Stage 5 H5 / Stage 18 L1 surfaces.

## Local smoke

```bash
# From repo root — adjust host/port to your API
curl -sS "http://127.0.0.1:8000/api/v1/metrics" | head
curl -sS "http://127.0.0.1:8000/api/v1/health/ready"

docker run --rm -p 9090:9090 \
  -v "$PWD/ops/prometheus:/etc/prometheus" \
  prom/prometheus:v2.54.1 \
  --config.file=/etc/prometheus/prometheus.yml
```

Open `http://127.0.0.1:9090` and confirm target `ribdigi-backend` and rules under **Alerts**. Blackbox job stays down until a blackbox_exporter is present — operators may curl readiness instead.

## Deferred

- Hosted Grafana-as-a-service Complete (Stage 28 A1 packages examples under `ops/grafana/` — see `docs/GRAFANA_PACK_MVP.md`)
- Alertmanager → PagerDuty production wiring Complete
- Centralized SIEM

See `docs/OPS_MONITORING_MVP.md` and `docs/GRAFANA_PACK_MVP.md` (`test_grafana_pack_a1.py`).
