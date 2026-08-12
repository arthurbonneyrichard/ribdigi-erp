# Agent notes

## Cursor Cloud specific instructions

### Services
- **Backend** (FastAPI): typically `cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000` with `DATABASE_URL`, `REDIS_URL`, `RABBITMQ_URL` pointing at localhost in this VM.
- **Frontend** (Next.js): `cd frontend && npm run dev` (port 3000).
- **Redis + RabbitMQ + Celery worker/beat**: required for rate limits and scheduled jobs. Compose definitions live in root `docker-compose.yml`; ops sketches in `ops/celery/`.
- Standard lint/test/run commands: see root README / `backend` and `frontend` package scripts. Reliability packaging: `docs/CELERY_RELIABILITY_RUNBOOK.md`, `docs/DR_WAL_PITR_RUNBOOK.md`.

### Non-obvious gotchas
- **Celery does not auto-reload.** After changing `backend/app/jobs.py`, `tasks.py`, or beat schedule, restart `celery_worker` and `celery_beat` or workers keep stale handler maps / crash on unknown jobs.
- **`run_async` uses one event loop per worker process** so sequential Celery tasks do not hit async SQLAlchemy “Future attached to a different loop” errors. Do not switch back to bare `asyncio.run()` per task without disposing the engine.
- Deep readiness: `GET /api/v1/health/ready` (and `?deep=true`) probes DB + Redis + Celery broker; shallow `/health` stays liveness-only.
- Admin job triggers: `GET /api/v1/jobs` (company_admin+) and `POST /api/v1/jobs/{name}/run` (**super_admin** only). Pass `X-Tenant-ID` as the JWT `tenant_id` UUID (slug mismatch → cross-tenant 403).
- Rate-limit tests: force `RATE_LIMIT_BACKEND=memory` + `rate_limiter.reset_for_tests()` under TestClient to avoid Redis event-loop flakes.
- - **Metrics / request logs:** `GET /api/v1/metrics` (Prometheus text; `METRICS_ENABLED`); structured JSON via `ribdigi.request` + `X-Request-ID` (`REQUEST_LOG_ENABLED`). Operator scrape/alerts: `ops/prometheus/`, Grafana examples: `ops/grafana/`. See `docs/OPS_MONITORING_MVP.md`.
- Do not commit `.devdata/` or `dump.rdb`.
