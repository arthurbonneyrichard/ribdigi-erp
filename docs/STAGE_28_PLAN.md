# Stage 28 Plan — Staging Certification Fidelity

**Status:** Open — R1 next (ADR-061)  
**Base:** Operator PITR Drill Pack + Staging GHA Workflow + Grafana/Alertmanager Packaging + 1000-VU Cert Pack → Staging Certification Fidelity  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Open ADR:** [ADR-061](ADR_061_STAGE28_OPEN.md)

Stage 28 closes the owner product outline after Stage 27 freeze: **Operator PITR Drill Packaging + Staging GHA Deploy Workflow + Grafana/Alertmanager Packaging + Operator 1000-VU Certificate Pack → Staging Certification Fidelity**. Stages 26–27 delivered Complete (MVP) ops platform and release packaging with honest Remaining for live staging drills, hosted observability, staging-only deploy workflows, and ~1000-VU certificates. This track extends proven Stage 26/27 assets (`DR_WAL_PITR_RUNBOOK.md`, `ops/k8s/`, `OPS_MONITORING_MVP.md`, `LOAD_CAPACITY_MVP.md`, `ops/security/zap-baseline.example.yml`) with operator certification packaging — **not** inventing live PITR success, green GHA→prod, hosted Grafana-as-a-service Complete, or forged 1000-VU certificates without artifacts — and **not** paid billing, schema-per-tenant, i18n packs, ADR-003/005, Open Banking, tax e-file, external LLM/Prophet, or reopening Stages 1–27.

## Product outline (owner)

```
Operator PITR Drill Pack
        +
Staging GHA Deploy Workflow
        +
Grafana / Alertmanager Packaging
        +
Operator 1000-VU Cert Pack
        ↓
Staging Certification Fidelity
```

## Delivery rules

1. One workstream at a time (full AC + automated tests before the next).
2. Prefer extending proven Stage 26/27 ops patterns — do not invent fake drill/deploy/Grafana/1000-VU success.
3. No demo data / fake success. Alembic only when schema is required.
4. After each feature: tests → commit → push → PR update.
5. Do not reopen Stage 1–27 feature scopes. Main `ci.yml` stays deploy-free (**Stage 18 C1**); staging workflows stay separate templates.
6. Deferred ADRs (001–006), vendor pen test purchase, and production cutover stay deferred unless explicitly in this plan.

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **R1** | Operator PITR drill packaging / evidence harness | P0 | PENDING |
| **G1** | Staging GHA deploy workflow (not main `ci.yml`) | P0 | PENDING |
| **A1** | Grafana / Alertmanager operator packaging | P0 | PENDING |
| **C1** | Operator ~1000-VU certificate pack | P1 | PENDING |
| **D1** | Spec / readiness / launch / deploy / security fidelity sync | P2 | PENDING |
| **H28x** | Stage 28 exit criteria + freeze ADR | Exit | PENDING |

## Explicitly out of this pass

- Paid billing (ADR-002); schema-per-tenant (ADR-001); i18n packs (ADR-006)
- User↔store membership (ADR-005); hard-delete with archival (ADR-003)
- Open Banking; tax e-file portals
- Claiming hosted Grafana/PagerDuty/SIEM as deployed-by-default SaaS Complete
- Live production cluster cutover / main `ci.yml` deploy jobs
- Vendor-purchased penetration test certificate
- Forged production LAUNCH §7 sign-off
- Multi-bin; FIFO/LIFO/WA; PO Kanban polish; vendor USB/serial POS drivers
- Richer WYSIWYG template designer; restore-to-new-tenant
- External LLM / Prophet / IsolationForest; PO OCR auto-apply
- Reopening Stages 1–27 frozen feature scopes

## R1 acceptance criteria

- [ ] Operator PITR drill packaging — checklist + evidence path extending `docs/DR_WAL_PITR_RUNBOOK.md` / `ops/postgres/` (not fake CI PITR success).
- [ ] Durable artifact path under `/opt/cursor/artifacts/dr/` (or equivalent).
- [ ] Automated proof: `backend/tests/test_pitr_drill_pack_r1.py`.
- [ ] PRODUCTION_READINESS WAL Remaining honesty updated.
- [ ] Plan / launch / roadmap cite Stage 28 R1.

## G1 acceptance criteria

- [ ] Staging-only GHA deploy workflow template (Helm/kubectl) — **not** wired into main `.github/workflows/ci.yml` (Stage 18 C1).
- [ ] Operator docs + secrets requirements; no invented green staging apply.
- [ ] Automated proof: `backend/tests/test_staging_gha_g1.py`.
- [ ] DEPLOYMENT_GUIDE / K8S_DEPLOY_MVP honesty updated.
- [ ] Plan / launch / roadmap cite Stage 28 G1.

## A1 acceptance criteria

- [ ] Grafana / Alertmanager operator packaging extending `docs/OPS_MONITORING_MVP.md` / `ops/prometheus/` (dashboards/alerts as examples — not hosted SaaS Complete).
- [ ] Automated proof: `backend/tests/test_grafana_pack_a1.py`.
- [ ] PRODUCTION_READINESS monitoring Remaining honesty updated.
- [ ] Plan / launch / roadmap cite Stage 28 A1.

## C1 acceptance criteria

- [ ] Operator ~1000-VU certificate pack extending `docs/LOAD_CAPACITY_MVP.md` / `backend/loadtest/` (checklist + artifact schema — not forged VU certificate).
- [ ] Automated proof: `backend/tests/test_load_cert_pack_c1.py`.
- [ ] PRODUCTION_READINESS load Remaining honesty updated.
- [ ] Plan / launch / roadmap cite Stage 28 C1.

## D1 acceptance criteria

- [ ] `docs/STAGE_28_FIDELITY.md` maps R1–C1 evidence → readiness / launch / deploy / security docs.
- [ ] PRODUCTION_READINESS / LAUNCH_CHECKLIST / DEVELOPMENT_ROADMAP / DEPLOYMENT_GUIDE / SECURITY_GUIDE cite Stage 28 D1.
- [ ] Automated proof: `backend/tests/test_stage28_fidelity_d1.py`.

## H28x acceptance criteria

- [ ] Exit criteria document with no CRITICAL/MISSING rows for R1–D1 / H28x — `docs/STAGE_28_EXIT_CRITERIA.md`.
- [ ] Scope freeze ADR accepted — `docs/ADR_062_STAGE28_FREEZE.md` (number reserved at close).
- [ ] LAUNCH_CHECKLIST / DEVELOPMENT_ROADMAP / PRODUCTION_READINESS cite exit + freeze.
- [ ] Automated proof: `backend/tests/test_stage28_exit_h28x.py`.
- [ ] Stages 1–27 freezes remain; Stage 29+ requires explicit open ADR after CONTINUE/NEXT.

## Sign-off

Stage 28 open under ADR-061. R1 next. Stages 1–27 remain frozen for their scopes.
