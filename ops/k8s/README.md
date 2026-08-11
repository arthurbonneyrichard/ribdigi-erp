# Kubernetes operator scripts (Stage 26 K1)

| File | Role |
|------|------|
| `helm-install-staging.sh.example` | `helm upgrade --install` with staging values |
| `staging-smoke.sh.example` | Rollout + `/api/v1/health/ready` + metrics smoke |

These are **operator templates** — not executed by CI. Main `.github/workflows/ci.yml` stays deploy-free (Stage 18 C1).

Authoritative doc: `docs/K8S_DEPLOY_MVP.md`.
