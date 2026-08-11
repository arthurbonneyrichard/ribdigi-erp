# Kubernetes operator scripts (Stage 26 K1)

| File | Role |
|------|------|
| `helm-install-staging.sh.example` | `helm upgrade --install` with staging values |
| `staging-smoke.sh.example` | Rollout + `/api/v1/health/ready` + metrics smoke |
| `deploy-staging.example.yml` | Staging-only GHA workflow template (Stage 28 G1) |

These are **operator templates** — not executed by CI. Main `.github/workflows/ci.yml` stays deploy-free (Stage 18 C1). Copy `deploy-staging.example.yml` into `.github/workflows/` only when kubeconfig / registry secrets and a real staging cluster exist — do not treat the disabled stub as a green apply.

Authoritative docs: `docs/K8S_DEPLOY_MVP.md`, `docs/STAGING_GHA_MVP.md` (`test_staging_gha_g1.py`).
