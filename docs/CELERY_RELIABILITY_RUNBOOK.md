# Celery / Redis / RabbitMQ reliability runbook (MVP)

**Workstream:** Celery reliability R1  
**Evidence:** `/opt/cursor/artifacts/ops/celery_reliability_r1.json` (`backend/tests/test_celery_reliability_r1.py`)  
**Checklist:** `ops/celery/celery-reliability-checklist.json`

## Topology

| Role | Default | Notes |
|------|---------|-------|
| Broker | RabbitMQ (`CELERY_BROKER_URL` / `RABBITMQ_URL`) | Required when `CELERY_ENABLED=true` |
| Results | Redis DB `/1` (derived from `REDIS_URL`) | Celery result backend |
| Rate limits | Redis DB `/0` (`REDIS_URL`) | Memory fallback unless `RATE_LIMIT_REQUIRE_REDIS=true` |
| Worker | `celery -A app.celery_app.celery worker` | `task_acks_late`, prefetch=1 |
| Beat | `celery -A app.celery_app.celery beat` | Interval schedule from settings |

Compose services: `redis`, `rabbitmq`, `celery_worker`, `celery_beat` in root `docker-compose.yml`. Drill sketch: `ops/celery/docker-compose.celery-drill.example.yml`.

## Intended production workloads (non-AI)

| Handler / beat key | Interval setting |
|--------------------|------------------|
| `scan_low_stock` / `scan-low-stock` | `CELERY_LOW_STOCK_INTERVAL_MINUTES` |
| `scan_payment_due` / `scan-payment-due` | `CELERY_PAYMENT_DUE_INTERVAL_MINUTES` |
| `scan_quotation_expiry` / `scan-quotation-expiry` | `CELERY_QUOTATION_EXPIRY_INTERVAL_MINUTES` |
| `generate_recurring_expenses` / `generate-recurring-expenses` | `CELERY_RECURRING_INTERVAL_MINUTES` |
| `run_due_backups` / `run-due-backups` | `CELERY_BACKUP_INTERVAL_MINUTES` |
| `scan_trial_lifecycle` / `scan-trial-lifecycle` | `CELERY_TRIAL_INTERVAL_MINUTES` |
| `run_due_report_emails` / `run-due-report-emails` | `CELERY_REPORT_EMAIL_INTERVAL_MINUTES` |
| `refresh_fx_rates` / `refresh-fx-rates` | `CELERY_FX_INTERVAL_MINUTES` |
| `sync_bank_feeds` / `sync-bank-feeds` | `CELERY_BANK_FEED_INTERVAL_MINUTES` |
| `archive_cold_audit_logs` / `archive-cold-audit-logs` | `CELERY_AUDIT_ARCHIVE_INTERVAL_MINUTES` |
| `retry_due_webhooks` / `retry-due-webhooks` | `CELERY_WEBHOOK_RETRY_INTERVAL_SECONDS` |

### AI-related (rule-based; no LLM nightly)

| Handler / beat key | Interval setting |
|--------------------|------------------|
| `scan_ai_security_alerts` / `scan-ai-security-alerts` | `CELERY_AI_SECURITY_INTERVAL_MINUTES` |

Admin APIs:

- `GET /api/v1/jobs` — lists handlers + full beat interval map (`celery_enabled`, broker, result backend).
- `POST /api/v1/jobs/{name}/run` — sync run (default) or `?enqueue=true` (requires `CELERY_ENABLED`).

## Health probes

- `GET /api/v1/health` — shallow liveness (`deep=false`).
- `GET /api/v1/health?deep=true` — DB + Redis + Celery broker checks.
- `GET /api/v1/health/ready` — always deep; **503** when overall status is `error` (hard DB failure, or required Redis failure).

Broker down while Celery is enabled reports `celery_broker.status=degraded` (overall `degraded`, HTTP 200) so liveness is preserved while readiness operators can alert.

## Operator verify (not claimed by CI)

1. Start Redis + RabbitMQ + API + worker + beat.
2. Confirm `GET /api/v1/health/ready` shows `database`/`redis`/`celery_broker` ok.
3. As `super_admin`, `GET /api/v1/jobs` shows all registered handlers and beat intervals (including `scan_ai_security_alerts`).
4. `POST /api/v1/jobs/scan_low_stock/run` (sync) returns tenant results.
5. Optional: `?enqueue=true` and confirm worker consumes the task.

**Gotcha:** Celery workers do not auto-reload. After changing `jobs.py` / `tasks.py` / beat schedule, restart `celery_worker` and `celery_beat`. `run_async` keeps one event loop per worker process so sequential tasks do not hit async SQLAlchemy “different loop” errors.

Flags in checklist / evidence (honesty):

- `live_broker_soak_executed: false` until staging soak is logged.
- `ai_nightly_claimed: false` — LLM/nightly AI forecast jobs remain under the AI functions gate; rule-based `scan_ai_security_alerts` is registered.
- `ci_queue_drained_claimed: false` — packaging tests do not prove queue drain.

## Remaining (post-MVP / other gates)

- AI nightly jobs (deferred to AI section).
- Live broker soak + on-call alert wiring (Monitoring gate).
- Managed K8s HPA for workers (Kubernetes gate).
