# Ops Monitoring MVP (Stage 18 L1 + Stage 26 M1)

**Status:** Documented — Stage 26 M1 scrape / alert / log-ship fidelity  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Related:** Stage 5 H5 (`test_health_metrics_h5.py`), Stage 18 L1 (`test_request_logging_l1.py`), Stage 26 M1 (`test_ops_monitoring_m1.py`)

This is the **MVP monitoring surface**: live health/metrics/logs plus versioned Prometheus scrape, alert rules, and log-shipping operator hooks. It is **not** a claim that a hosted Grafana/Alertmanager/PagerDuty/SIEM stack is deployed in CI or production by default.

## Structured request / error logs

Middleware: `RequestLoggingMiddleware` (`backend/app/request_logging.py`).

- Logger name: `ribdigi.request`
- Format: one JSON object per line (stdlib logging)
- Header: `X-Request-ID` accepted on input and always set on the response (CORS-exposed)
- Env: `REQUEST_LOG_ENABLED=true` (default), `LOG_LEVEL=INFO`

### Fields

| Field | Meaning |
|-------|---------|
| `event` | `http_request` or `http_error` |
| `request_id` | Correlation id |
| `method` / `path` | HTTP method and path |
| `status` | Response status code |
| `latency_ms` | End-to-end middleware latency |
| `tenant_id` | From JWT / `X-Tenant-ID` when present |
| `user_id` | From JWT `sub` when present |
| `error_code` | Safe code only (e.g. `INSUFFICIENT_STOCK`, `UNAUTHENTICATED`) — no bodies/PII |

Health (`/api/v1/health*`) and `/api/v1/metrics` are **not** logged at INFO to avoid scrape noise.

Ship these lines with your container log driver / Fluent Bit / cloud logging. Do not treat them as the financial audit trail (see BR-17 / hash-chained audit).

## Health & readiness

| Endpoint | Role |
|----------|------|
| `GET /api/v1/health` | Liveness (shallow; includes non-sensitive security posture) |
| `GET /api/v1/health?deep=true` | Dependency probe (database, Redis, Celery broker) |
| `GET /api/v1/health/ready` | Readiness — same deep checks; **503** when hard deps fail |

Use `health/ready` for orchestrator readiness probes. Shallow `/health` stays safe for load balancers that must not fail on Redis blips unless you opt into deep checks.

## Metrics

| Endpoint | Role |
|----------|------|
| `GET /api/v1/metrics` | Prometheus text exposition (`METRICS_ENABLED`, default on) |

Series include `ribdigi_up`, `ribdigi_http_requests_total{method,status}`, and duration sum/count by coarse `path_group` (avoids high cardinality).

## Prometheus scrape (Stage 26 M1)

Versioned config: `ops/prometheus/prometheus.yml` + `ops/prometheus/README.md`.

- Job `ribdigi-backend` scrapes `metrics_path: /api/v1/metrics`
- Job `ribdigi-ready` documents blackbox probing of `/api/v1/health/ready` (requires operator blackbox_exporter)
- Not started by default `docker-compose` or CI

## Alert rules (Stage 26 M1)

Versioned rules: `ops/prometheus/alerts/ribdigi.yml`.

| Alert | Signal |
|-------|--------|
| `RibdigiDown` | `ribdigi_up` missing/zero |
| `RibdigiHighErrorRate` | 5xx rate from `ribdigi_http_requests_total` > 5% for 5m |
| `RibdigiHighLatency` | mean duration from sum/count > 500ms for 10m |
| `RibdigiNotReady` | blackbox `probe_success` for readiness job == 0 |
| `RibdigiRabbitMQQueueDepthHigh` | optional `rabbitmq_exporter` (`rabbitmq_queue_messages`) — not emitted by the app |

Wire Alertmanager → PagerDuty in the operator environment when ready; hosted PagerDuty is **Remaining**.

## Log shipping hooks (Stage 26 M1)

Example: `ops/logging/fluent-bit-ribdigi.conf.example` — parse `ribdigi.request` JSON lines and forward (stdout / ES / CloudWatch / Loki via operator OUTPUT).

Docker `json-file` / journald drivers also capture process stdout when `REQUEST_LOG_ENABLED=true`. Correlate with the `X-Request-ID` response header. This is **not** a centralized SIEM deployment claim.

## Explicitly deferred (hosted ops)

- Hosted Grafana dashboards / Alertmanager routing / PagerDuty
- Distributed tracing (OpenTelemetry) backends
- Full log PII scanners / SIEM rulesets
- Certified capacity / SLO burn-rate alerts (Stage 26 C1)

## Operator smoke

1. `curl -sS "$API/api/v1/health/ready"` → 200 with `checks.database.status=ok`
2. `curl -sS "$API/api/v1/metrics" | head` → `ribdigi_up 1`
3. Call any authenticated API with `X-Request-ID: drill-1` and confirm the response echoes the header and a JSON log line contains `"request_id":"drill-1"`.
4. Confirm `ops/prometheus/prometheus.yml` scrapes `/api/v1/metrics` and `ops/prometheus/alerts/ribdigi.yml` names `RibdigiDown` / `RibdigiHighErrorRate`.
5. Optionally mount `ops/prometheus` into a local Prometheus container per `ops/prometheus/README.md`.
