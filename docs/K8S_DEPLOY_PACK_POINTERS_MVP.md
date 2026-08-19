# K8s Deploy Pack Pointers MVP — Stage 206 P1

**Status:** Complete (MVP packaging) — Stage 206 P1  
**Evidence:** `backend/tests/test_stage206_pointers_p1.py`  
**Register:** `ops/mvp/k8s-deploy-pack-pointers.json`  
**Related:** [K8S_DEPLOY_REMAINING_GATE_MVP.md](K8S_DEPLOY_REMAINING_GATE_MVP.md) · [K8S_DEPLOY_MVP.md](K8S_DEPLOY_MVP.md) · [STAGING_GHA_REMAINING_GATE_MVP.md](STAGING_GHA_REMAINING_GATE_MVP.md) · [STAGE_206_PLAN.md](STAGE_206_PLAN.md)

Pointers into Stage 26 K1 k8s deploy, Stage 205 staging GHA remaining-gate, and Stage 18 C1 deploy-free main CI. Every pointer keeps live cluster deploy non-claimed.

## Classification

| Flag | Value |
|------|-------|
| `packaging_complete` | true |
| `live_cluster_deploy_claimed` | **false** |
| `ci_deploy_claimed` | **false** |
| `go_live_claimed` | **false** |
| `live_staging_apply_claimed` | **false** |

## Pack pointers

| Gate theme | Primary docs |
|------------|--------------|
| Stage 26 K1 k8s deploy | `K8S_DEPLOY_MVP.md` / `helm/ribdigi/` / `k8s/` |
| Helm install helper | `ops/k8s/helm-install-staging.sh.example` |
| Staging smoke helper | `ops/k8s/staging-smoke.sh.example` |
| Stage 205 staging GHA remaining-gate | `STAGING_GHA_REMAINING_GATE_MVP.md` (orthogonal) |
| Stage 18 C1 deploy-free CI | `.github/workflows/ci.yml` |
| Production readiness | `PRODUCTION_READINESS.md` |

## Explicit non-claim

1. Stage 26 K1 packaging Completes are **not** live cluster deploy Complete.
2. Stage 18 C1 deploy-free main CI is **not** live deploy Complete.
3. Do not claim main `ci.yml` deploy wiring from this index.
4. Do not claim live cluster deploy Complete from this pointer index.
5. Distinct from Stage 205 staging GHA remaining-gate.

## Explicitly not claimed

- Live cluster deploy Completes
- Go-live / live staging GHA apply Completes
