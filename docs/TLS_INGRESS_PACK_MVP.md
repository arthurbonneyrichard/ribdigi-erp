# TLS Ingress Pack MVP — Cert-manager / TLS Operator Packaging

**Status:** Complete (MVP) — Stage 29 T1  
**Evidence:** `backend/tests/test_tls_ingress_t1.py` · `/opt/cursor/artifacts/k8s/stage29_t1_tls_ingress.json`  
**Checklist map:** `ops/k8s/tls-checklist.json`  
**Examples:** `ops/k8s/cluster-issuer.example.yaml` · `ops/k8s/ingress-tls.example.yaml`  
**Related:** [K8S_DEPLOY_MVP.md](K8S_DEPLOY_MVP.md) (Stage 26 K1) · `helm/ribdigi/templates/ingress.yaml`

This is the **MVP cert-manager / TLS ingress packaging surface**: ClusterIssuer + Ingress TLS examples + checklist extending Stage 26 K1. It is **not** live Let’s Encrypt issuance Complete and does **not** claim production TLS cutover already happened.

## Classification

| Class | Meaning |
|-------|---------|
| `operator_required` | Install cert-manager, apply issuers/Ingress, confirm Certificate Ready + HTTPS health |
| `ci_proven` | Helm Ingress template paths (Stage 26 K1) + this pack honesty |
| `deferred` | Live ACME issuance Complete in CI; production cutover TLS; Istio mTLS |

## Probe notes

After TLS is Ready on staging:

1. `curl -fsS https://<host>/api/v1/health` → 200  
2. Prefer HSTS at the ingress / edge (not forged by packaging alone)  
3. Keep main `.github/workflows/ci.yml` deploy-free (**Stage 18 C1**)

## Automation hooks

1. Maintain `ops/k8s/tls-checklist.json` (synced by `test_tls_ingress_t1.py`).
2. Examples stay under `ops/k8s/` — operators apply when DNS + cert-manager exist.
3. CI proves packaging honesty only: `letsencrypt_issued: false`, `tls_cutover_claimed: false`.

## Explicitly not claimed

- Green Let’s Encrypt Certificate Ready from CI
- Production TLS cutover without ops change-log evidence
- Istio / Linkerd mTLS mesh Complete
- Treating Stage 26 K1 / Stage 29 T1 Complete as “TLS cutover done”

## Sign-off

Stage 29 T1 is met when this doc + checklist + ClusterIssuer/Ingress examples + evidence JSON exist, `test_tls_ingress_t1.py` passes, and DEPLOYMENT_GUIDE / K8S_DEPLOY_MVP / launch / roadmap cite Stage 29 T1 without inventing live issuance success.

See also Stage 207 Tenant MVP TLS Ingress remaining-gate index fidelity (`docs/TLS_INGRESS_REMAINING_GATE_MVP.md`, ADR-420 / ADR-421) — packaging non-claim as live TLS ingress Complete.
