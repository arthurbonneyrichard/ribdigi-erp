# Ops Monitoring MVP (Stage 18 L1)

**Status:** Documented  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Related:** Stage 5 H5 (`test_health_metrics_h5.py`), Stage 18 L1 (`test_request_logging_l1.py`)

This is the **MVP-lite** monitoring surface. It is **not** a full Prometheus/Grafana/PagerDuty stack (deferred post-MVP).

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

Scrape with Prometheus when available; until then, curl the endpoint in ops drills.

## Explicitly out of MVP

- Grafana dashboards / Alertmanager / PagerDuty
- Distributed tracing (OpenTelemetry) backends
- Full log PII scanners / SIEM rulesets
- Certified capacity / SLO burn-rate alerts

## Operator smoke

1. `curl -sS "$API/api/v1/health/ready"` → 200 with `checks.database.status=ok`
2. `curl -sS "$API/api/v1/metrics" | head` → `ribdigi_up 1`
3. Call any authenticated API with `X-Request-ID: drill-1` and confirm the response echoes the header and a JSON log line contains `"request_id":"drill-1"`.
