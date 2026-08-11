# Kubernetes Deploy MVP (Stage 26 K1)

**Status:** Documented — Stage 26 K1 chart / manifest / smoke fidelity; Stage 28 G1 staging GHA template packaging  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Related:** Stage 18 C1 (`test_ci_prod_config_c1.py`), Stage 26 K1 (`test_k8s_deploy_k1.py`), Stage 28 G1 (`test_staging_gha_g1.py`)  
**Evidence (K1):** `/opt/cursor/artifacts/k8s/stage26_k1_deploy_fidelity.json`  
**Evidence (G1):** `/opt/cursor/artifacts/k8s/stage28_g1_staging_gha.json` · [STAGING_GHA_MVP.md](STAGING_GHA_MVP.md)

This is the **MVP Kubernetes deploy surface**: versioned Helm chart + hardened `k8s/` manifests with correct health probes, secret refs, and operator staging smoke scripts. Stage 28 G1 adds an optional staging GHA workflow **template** under `ops/k8s/` (not main `ci.yml`). It is **not** a claim that CI deploys to a live cluster or that managed data-plane services are provisioned by the chart.

## Artifacts

| Path | Role |
|------|------|
| `helm/ribdigi/` | Chart (`Chart.yaml`, values, templates) |
| `k8s/` | kubectl-friendly hardened manifests |
| `ops/k8s/helm-install-staging.sh.example` | Install helper |
| `ops/k8s/staging-smoke.sh.example` | Rollout + ready + metrics smoke |
| `ops/k8s/deploy-staging.example.yml` | Staging-only GHA template (Stage 28 G1) — **not** in main `ci.yml` |
| `ops/k8s/cluster-issuer.example.yaml` | Cert-manager ClusterIssuer examples (Stage 29 T1) |
| `ops/k8s/ingress-tls.example.yaml` | Ingress + TLS example (Stage 29 T1) |
| `ops/k8s/tls-checklist.json` | TLS operator checklist (Stage 29 T1) |
| `.env.production.example` | Secret source template (Stage 18 C1) |

## Probe contract

| Probe | Path | Notes |
|-------|------|-------|
| Liveness | `GET /api/v1/health` | Shallow; load-balancer safe |
| Readiness | `GET /api/v1/health/ready` | Deep deps; **503** when hard deps fail |

Do not use bare `/health` or `/ready` paths from older aspirational docs.

## Workloads

- **Backend** — `alembic upgrade head && uvicorn … --workers 2` (matches `docker-compose.prod.yml`)
- **Frontend** — Next.js image
- **Celery worker / beat** — `celery -A app.celery_app.celery …` (matches compose)
- **Migration Job** — Helm pre-install/upgrade hook + flat `k8s/migration-job.yaml`

Managed PostgreSQL / Redis / RabbitMQ / object storage are **external**. Create `ribdigi-secrets` from `.env.production` (keys documented in `helm/ribdigi/templates/secrets.example.yaml` and `values.yaml` `requiredSecretKeys`).

## Operator staging smoke

1. Build/push images from `backend/Dockerfile` and `frontend/Dockerfile` (operator registry).
2. `kubectl create secret generic ribdigi-secrets --from-env-file=.env.production -n ribdigi-staging`
3. Run `ops/k8s/helm-install-staging.sh.example` (or `kubectl apply -f k8s/…`).
4. Run `ops/k8s/staging-smoke.sh.example` — expects `/api/v1/health/ready` 200 and `ribdigi_up` in metrics.

CI writes strategy/fidelity evidence only (`stage26_k1_deploy_fidelity.json` with `gha_staging_deploy_deferred=true`). Stage 28 G1 packaging evidence (`stage28_g1_staging_gha.json`) keeps `live_staging_apply_claimed=false` and `gha_staging_wired_into_main_ci=false`.

## Staging GHA template (Stage 28 G1)

Optional workflow template: `ops/k8s/deploy-staging.example.yml` — documented in [STAGING_GHA_MVP.md](STAGING_GHA_MVP.md). Operators copy into `.github/workflows/` only when `KUBE_CONFIG` / registry secrets and a real staging cluster exist. Disabled stub in the template must not be treated as a green apply. Main `.github/workflows/ci.yml` stays deploy-free.

## Cert-manager / TLS packaging (Stage 29 T1)

Authoritative pack: [TLS_INGRESS_PACK_MVP.md](TLS_INGRESS_PACK_MVP.md) · `ops/k8s/cluster-issuer.example.yaml` · `ops/k8s/ingress-tls.example.yaml` · `ops/k8s/tls-checklist.json`.

Packaging evidence keeps `letsencrypt_issued: false`, `tls_cutover_claimed: false`. Helm `templates/ingress.yaml` remains path-aligned (`/api` → backend, `/` → frontend); operators enable TLS via the examples when DNS + cert-manager exist.

## Relationship to Stage 18 C1

Single-node production Compose (`docker-compose.prod.yml` + `.env.production.example`) remains a valid MVP path. Main `.github/workflows/ci.yml` stays **deploy-free** (pytest + frontend build). K1 / G1 do not add `kubectl`/`helm upgrade` to that workflow.

## Explicitly deferred

- Live GHA → staging/production cluster apply (template packaging Complete MVP — Stage 28 G1; execution Remaining)
- In-cluster Postgres/Redis/RabbitMQ
- Live Let’s Encrypt issuance / production TLS **cutover** (Stage 29 T1 packs examples only)
- Istio / full NetworkPolicy / HPA enforcement without staging proof

## Sign-off

Stage 26 K1 is met when the chart/manifests encode the probe contract, operator smoke scripts exist, the guard test passes, and PRODUCTION_READINESS Kubernetes gate is Complete (MVP) with Remaining limited to live cluster apply. Stage 28 G1 is met when `docs/STAGING_GHA_MVP.md` + `ops/k8s/deploy-staging.example.yml` + `test_staging_gha_g1.py` pass without claiming live apply. Stage 29 T1 is met when `docs/TLS_INGRESS_PACK_MVP.md` + issuer/Ingress examples + `test_tls_ingress_t1.py` pass without inventing live ACME issuance.
