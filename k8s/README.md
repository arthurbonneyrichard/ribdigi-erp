# Kubernetes manifests (Stage 26 K1)

Hardened kubectl path for RIBDIGI BUSINESS ERP. Prefer the Helm chart at `helm/ribdigi/` for installs.

| File | Role |
|------|------|
| `namespace.yaml` | `ribdigi-staging` / `ribdigi-production` |
| `backend.yaml` | Deployment + Service with `/api/v1/health` + `/api/v1/health/ready` probes |
| `frontend.yaml` | Frontend Deployment + Service |
| `celery-worker.yaml` / `celery-beat.yaml` | Celery workloads |
| `migration-job.yaml` | `alembic upgrade head` |

## Assumptions

- Managed PostgreSQL / Redis / RabbitMQ / object storage (create `ribdigi-secrets` from `.env.production.example`)
- Images built from `backend/Dockerfile` and `frontend/Dockerfile`

## Operator smoke

See `docs/K8S_DEPLOY_MVP.md` and `ops/k8s/staging-smoke.sh.example`.

**Deferred:** live GHA → staging cluster apply (main CI remains deploy-free per Stage 18 C1).
