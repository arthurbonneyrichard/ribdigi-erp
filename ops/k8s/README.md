# Kubernetes operator scripts (Stage 26 K1)

| File | Role |
|------|------|
| `helm-install-staging.sh.example` | `helm upgrade --install` with staging values |
| `staging-smoke.sh.example` | Rollout + `/api/v1/health/ready` + metrics smoke |
| `deploy-staging.example.yml` | Staging-only GHA workflow template (Stage 28 G1) |
| `cluster-issuer.example.yaml` | Cert-manager ClusterIssuer examples (Stage 29 T1) |
| `ingress-tls.example.yaml` | Ingress + TLS example (Stage 29 T1) |
| `tls-checklist.json` | TLS operator checklist (Stage 29 T1) |

These are **operator templates** — not executed by CI. Main `.github/workflows/ci.yml` stays deploy-free (Stage 18 C1). Copy `deploy-staging.example.yml` into `.github/workflows/` only when kubeconfig / registry secrets and a real staging cluster exist — do not treat the disabled stub as a green apply. TLS examples require cert-manager + DNS — do not treat them as green Let’s Encrypt issuance.

Authoritative docs: `docs/K8S_DEPLOY_MVP.md`, `docs/STAGING_GHA_MVP.md` (`test_staging_gha_g1.py`), `docs/TLS_INGRESS_PACK_MVP.md` (`test_tls_ingress_t1.py`).
