# Helm chart — ribdigi (Stage 26 K1)

Production-shaped chart for RIBDIGI BUSINESS ERP. Assumes **managed** PostgreSQL, Redis, RabbitMQ, and object storage.

| Path | Role |
|------|------|
| `Chart.yaml` | Chart metadata |
| `values.yaml` | Defaults (probes, resources, secret name) |
| `values-staging.yaml` / `values-production.yaml` | Environment overlays |
| `templates/` | Backend/frontend/Celery/migration/Ingress |

## Install (operator staging)

```bash
kubectl create namespace ribdigi-staging
kubectl -n ribdigi-staging create secret generic ribdigi-secrets \
  --from-env-file=.env.production

helm upgrade --install ribdigi-staging ./helm/ribdigi \
  -f ./helm/ribdigi/values-staging.yaml \
  -n ribdigi-staging
```

Or use `ops/k8s/helm-install-staging.sh.example` + `ops/k8s/staging-smoke.sh.example`.

## Probe contract

| Probe | Path |
|-------|------|
| Liveness | `GET /api/v1/health` |
| Readiness | `GET /api/v1/health/ready` |

## Deferred

- Live GHA → staging cluster apply (main `ci.yml` stays deploy-free per Stage 18 C1)
- In-cluster Postgres/Redis/RabbitMQ
- Cert-manager / production TLS cutover automation

See `docs/K8S_DEPLOY_MVP.md`.
