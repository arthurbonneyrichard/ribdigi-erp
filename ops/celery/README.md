# Celery reliability ops pack

See `docs/CELERY_RELIABILITY_RUNBOOK.md` for topology, job matrix, health probes, and operator verify steps.

| File | Purpose |
|------|---------|
| `celery-reliability-checklist.json` | Operator checklist + honesty flags |
| `docker-compose.celery-drill.example.yml` | Local redis/rabbit/worker/beat sketch |

Packaging evidence: `/opt/cursor/artifacts/ops/celery_reliability_r1.json` from `backend/tests/test_celery_reliability_r1.py`.
