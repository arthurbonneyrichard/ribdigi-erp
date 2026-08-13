# Staging GHA Deploy MVP — Operator Workflow Packaging

**Status:** Complete (MVP) — Stage 28 G1  
**Evidence:** `backend/tests/test_staging_gha_g1.py` · `/opt/cursor/artifacts/k8s/stage28_g1_staging_gha.json`  
**Template:** `ops/k8s/deploy-staging.example.yml`  
**Related:** [K8S_DEPLOY_MVP.md](K8S_DEPLOY_MVP.md) (Stage 26 K1) · `ops/k8s/helm-install-staging.sh.example` · `ops/k8s/staging-smoke.sh.example`

This is the **MVP staging GitHub Actions deploy packaging surface**: a versioned workflow template that operators may copy into `.github/workflows/` when kubeconfig / registry secrets and a real staging cluster exist. It is **not** wired into main `.github/workflows/ci.yml` (Stage 18 C1) and does **not** invent a green staging apply.

## Classification

| Class | Meaning |
|-------|---------|
| `operator_required` | Provision staging cluster + `ribdigi-secrets`; copy template; set secrets; run `workflow_dispatch` |
| `ci_proven` | Chart/manifest/smoke packaging (Stage 26 K1) + this template honesty (`test_staging_gha_g1.py`) |
| `deferred` | Live GHA→staging apply Complete; production cutover via GHA (packaged separately as Stage 29 X1 — [CUTOVER_PACK_MVP.md](CUTOVER_PACK_MVP.md)); in-cluster data plane |

## Secrets requirements

| Secret | Purpose |
|--------|---------|
| `KUBE_CONFIG` | Base64 kubeconfig (or equivalent OIDC) for staging |
| `REGISTRY_USERNAME` / `REGISTRY_PASSWORD` | Push/pull images when private |
| `STAGING_BASE_URL` | Optional post-deploy smoke target |

Never commit real kubeconfigs or registry tokens. Prefer GitHub Environments (`staging`) with required reviewers.

## Automation hooks

1. Keep `ops/k8s/deploy-staging.example.yml` as the authoritative template (synced by `test_staging_gha_g1.py`).
2. Operators may alternatively run `helm-install-staging.sh.example` + `staging-smoke.sh.example` without GHA.
3. CI proves packaging honesty only: `gha_staging_wired_into_main_ci: false`, `live_staging_apply_claimed: false`.

## Explicitly not claimed

- Green `helm upgrade` / `kubectl apply` success from CI against a live cluster
- Adding `deploy:` / `kubectl` / `helm upgrade` jobs to main `ci.yml`
- Treating Stage 26 K1 / Stage 28 G1 Complete as “staging is continuously deployed”
- Production cutover success (see Stage 29 X1 `docs/CUTOVER_PACK_MVP.md` / `ops/k8s/deploy-production.example.yml` — packaging only)

## Sign-off

Stage 28 G1 is met when this doc + template + evidence JSON exist, `test_staging_gha_g1.py` passes, main `ci.yml` remains deploy-free, and DEPLOYMENT_GUIDE / K8S_DEPLOY_MVP / launch / roadmap cite Stage 28 G1 without inventing live apply success. Stage 29 X1 packages the production cutover harness without claiming live promote.

See also Stage 204 Tenant MVP Launch Cert remaining-gate index fidelity (`docs/LAUNCH_CERT_REMAINING_GATE_MVP.md`, ADR-414 / ADR-415).
