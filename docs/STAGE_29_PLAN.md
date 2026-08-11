# Stage 29 Plan — Operator Hardening & Production Cutover Fidelity

**Status:** Open — V1 next (ADR-063)  
**Base:** Vendor Pen-Test / ZAP Staging Pack + PgBouncer Soak / Helm Pooler Pack + Cert-manager / TLS Ingress Pack + Production Cutover Pack → Operator Hardening & Cutover Fidelity  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Open ADR:** [ADR-063](ADR_063_STAGE29_OPEN.md)

Stage 29 closes the owner product outline after Stage 28 freeze: **Vendor Pen-Test / ZAP Staging Packaging + PgBouncer Soak / Helm Pooler Packaging + Cert-manager / TLS Ingress Packaging + Production Cutover Packaging → Operator Hardening & Production Cutover Fidelity**. Stages 26–28 delivered Complete (MVP) ops platform, release, and staging-certification **packaging** with honest Remaining for live execution, purchased vendor pen tests, hosted SaaS observability, and production §7 sign-off. This track packages adjacent Remaining on proven Stage 26/27/28 assets (`SECURITY_SCAN_MVP.md`, `PGBOUNCER_MVP.md`, `K8S_DEPLOY_MVP.md`, `LAUNCH_CERT_MVP.md`) — **not** inventing purchased pen-test certificates, green live soak numbers, Let’s Encrypt issuance success, forged §7 sign-off, or re-packaging Stage 28 R1/G1/A1/C1 packs — and **not** paid billing, schema-per-tenant, i18n packs, ADR-003/005, Open Banking, tax e-file, external LLM/Prophet, or reopening Stages 1–28.

## Product outline (owner)

```
Vendor Pen-Test / ZAP Staging Pack
        +
PgBouncer Soak / Helm Pooler Pack
        +
Cert-manager / TLS Ingress Pack
        +
Production Cutover Pack
        ↓
Operator Hardening & Cutover Fidelity
```

## Delivery rules

1. One workstream at a time (full AC + automated tests before the next).
2. Prefer extending proven Stage 26–28 ops patterns — do not invent fake pen-test/soak/TLS/cutover success.
3. No demo data / fake success. Alembic only when schema is required.
4. After each feature: tests → commit → push → PR update.
5. Do not reopen Stage 1–28 feature scopes. Main `ci.yml` stays deploy-free (**Stage 18 C1**); staging/pen-test workflows stay separate templates.
6. Deferred ADRs (001–006), purchased vendor pen-test certificates, and forged production sign-off stay deferred unless explicitly in this plan.
7. Do not re-ship Stage 28 R1/G1/A1/C1 packs as new Complete — extend adjacent Remaining only.

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **V1** | Vendor pen-test / ZAP staging operator pack | P0 | PENDING |
| **B2** | PgBouncer soak / Helm pooler packaging | P0 | PENDING |
| **T1** | Cert-manager / TLS ingress packaging | P0 | PENDING |
| **X1** | Production cutover pack (LAUNCH §§1–3 / §7 harness) | P1 | PENDING |
| **D1** | Spec / readiness / launch / deploy / security fidelity sync | P2 | PENDING |
| **H29x** | Stage 29 exit criteria + freeze ADR | Exit | PENDING |

## Explicitly out of this pass

- Paid billing (ADR-002); schema-per-tenant (ADR-001); i18n packs (ADR-006)
- User↔store membership (ADR-005); hard-delete with archival (ADR-003)
- Open Banking; tax e-file portals
- Claiming hosted Grafana/PagerDuty/SIEM as SaaS Complete
- Live production cluster cutover via main `ci.yml` deploy jobs
- Purchased vendor penetration test certificate as Complete
- Forged production LAUNCH §7 Name/Date sign-off
- Re-packaging Stage 28 PITR / staging GHA / Grafana / 1000-VU packs as new Complete
- Forging live PITR / 1000-VU / GHA apply success
- Multi-bin; FIFO/LIFO/WA; PO Kanban polish; vendor USB/serial POS drivers
- Richer WYSIWYG template designer; restore-to-new-tenant
- External LLM / Prophet / IsolationForest; PO OCR auto-apply
- Reopening Stages 1–28 frozen feature scopes

## V1 acceptance criteria

- [ ] Vendor pen-test / ZAP staging operator packaging extending `docs/SECURITY_SCAN_MVP.md` / `ops/security/` (engagement checklist + evidence schema — not purchased cert / green live ZAP without target).
- [ ] Durable artifact path under `/opt/cursor/artifacts/security/` (or equivalent).
- [ ] Automated proof: `backend/tests/test_pentest_pack_v1.py`.
- [ ] PRODUCTION_READINESS OWASP Remaining honesty updated.
- [ ] Plan / launch / roadmap cite Stage 29 V1.

## B2 acceptance criteria

- [ ] PgBouncer soak / optional Helm pooler packaging extending `docs/PGBOUNCER_MVP.md` / `ops/postgres/` (soak checklist + pooler snippet — not live soak numbers / default in-cluster data plane Complete).
- [ ] Automated proof: `backend/tests/test_pgbouncer_soak_b2.py`.
- [ ] PRODUCTION_READINESS / DEPLOYMENT_GUIDE honesty updated.
- [ ] Plan / launch / roadmap cite Stage 29 B2.

## T1 acceptance criteria

- [ ] Cert-manager / TLS ingress operator packaging extending `docs/K8S_DEPLOY_MVP.md` / `helm/ribdigi/` or `ops/k8s/` (Ingress + ClusterIssuer examples — not live Let’s Encrypt issuance Complete).
- [ ] Automated proof: `backend/tests/test_tls_ingress_t1.py`.
- [ ] DEPLOYMENT_GUIDE / K8S_DEPLOY_MVP honesty updated.
- [ ] Plan / launch / roadmap cite Stage 29 T1.

## X1 acceptance criteria

- [ ] Production cutover pack extending `docs/LAUNCH_CERT_MVP.md` / Stage 28 G1 (cutover/rollback/secrets handoff checklist mapping LAUNCH §§1–3 / §7 — not forged §7 sign-off).
- [ ] Automated proof: `backend/tests/test_cutover_pack_x1.py`.
- [ ] LAUNCH_CHECKLIST / PRODUCTION_READINESS honesty updated.
- [ ] Plan / launch / roadmap cite Stage 29 X1.

## D1 acceptance criteria

- [ ] `docs/STAGE_29_FIDELITY.md` maps V1–X1 evidence → readiness / launch / deploy / security docs.
- [ ] PRODUCTION_READINESS / LAUNCH_CHECKLIST / DEVELOPMENT_ROADMAP / DEPLOYMENT_GUIDE / SECURITY_GUIDE cite Stage 29 D1.
- [ ] Automated proof: `backend/tests/test_stage29_fidelity_d1.py`.

## H29x acceptance criteria

- [ ] Exit criteria document with no CRITICAL/MISSING rows for V1–D1 / H29x — `docs/STAGE_29_EXIT_CRITERIA.md`.
- [ ] Scope freeze ADR accepted — `docs/ADR_064_STAGE29_FREEZE.md` (number reserved at close).
- [ ] LAUNCH_CHECKLIST / DEVELOPMENT_ROADMAP / PRODUCTION_READINESS cite exit + freeze.
- [ ] Automated proof: `backend/tests/test_stage29_exit_h29x.py`.
- [ ] Stages 1–28 freezes remain; Stage 30+ requires explicit open ADR after CONTINUE/NEXT.

## Sign-off

Stage 29 open under ADR-063. V1 next. Stages 1–28 remain frozen for their scopes.
