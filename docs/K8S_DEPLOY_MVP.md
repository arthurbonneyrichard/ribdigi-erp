# Kubernetes Deploy MVP (Stage 26 K1)

**Status:** Complete (MVP packaging) — chart / manifest / smoke fidelity  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Related:** Stage 26 K1 (`test_k8s_deploy_k1.py`); health/metrics from ops monitoring  
**Evidence:** `/opt/cursor/artifacts/k8s/stage26_k1_deploy_fidelity.json`

This is the **MVP Kubernetes deploy surface**: versioned Helm chart + hardened `k8s/` manifests with correct health probes, secret refs, and operator staging smoke scripts. It is **not** a claim that CI deploys to a live cluster or that managed data-plane services are provisioned by the chart.

## Artifacts

| Path | Role |
|------|------|
| `helm/ribdigi/` | Chart (`Chart.yaml`, values, templates) |
| `k8s/` | kubectl-friendly hardened manifests |
| `ops/k8s/helm-install-staging.sh.example` | Install helper |
| `ops/k8s/staging-smoke.sh.example` | Rollout + ready + metrics smoke |
| `.env.production.example` | Secret key template for `ribdigi-secrets` |

## Probe contract

| Probe | Path | Notes |
|-------|------|-------|
| Liveness | `GET /api/v1/health` | Shallow; load-balancer safe |
| Readiness | `GET /api/v1/health/ready` | Deep deps; **503** when hard deps fail |

Do not use bare `/health` or `/ready` paths from older aspirational docs.

## Workloads

- **Backend** — `alembic upgrade head && uvicorn …` (matches production compose intent)
- **Frontend** — Next.js image
- **Celery worker / beat** — `celery -A app.celery_app.celery …`
- **Migration Job** — Helm pre-install/upgrade hook + flat `k8s/migration-job.yaml`

Managed PostgreSQL / Redis / RabbitMQ / object storage are **external**. Create `ribdigi-secrets` from `.env.production` (keys documented in `helm/ribdigi/templates/secrets.example.yaml` and `values.yaml` `requiredSecretKeys`).

## Operator staging smoke

1. Build/push images from `backend/Dockerfile` and `frontend/Dockerfile` (operator registry).
2. `kubectl create secret generic ribdigi-secrets --from-env-file=.env.production -n ribdigi-staging`
3. Run `ops/k8s/helm-install-staging.sh.example` (or `kubectl apply -f k8s/…`).
4. Run `ops/k8s/staging-smoke.sh.example` — expects `/api/v1/health/ready` 200 and `ribdigi_up` in metrics.

CI writes packaging evidence only (`stage26_k1_deploy_fidelity.json` with `gha_staging_deploy_deferred=true`, `operator_staging_apply_required=true`). Main `.github/workflows/ci.yml` stays **deploy-free**.

## Explicitly deferred (Remaining)

- Live GHA → staging/production cluster apply (staging GHA / TLS / cutover packs)
- In-cluster Postgres/Redis/RabbitMQ
- Live Let’s Encrypt issuance / production TLS cutover
- Istio / full NetworkPolicy / HPA without staging proof

## Sign-off

Stage 26 K1 is met when the chart/manifests encode the probe contract, operator smoke scripts exist, `test_k8s_deploy_k1.py` passes, and PRODUCTION_READINESS Kubernetes gate is Complete (MVP) with Remaining limited to live cluster apply.
