# Stage 26 Plan — Production Platform & Ops Fidelity

**Status:** Open — M1 COMPLETE; W1 next (ADR-057)  
**Base:** Monitoring & Alerting + WAL/PITR + Kubernetes Deploy + Load Capacity → Ops Platform Fidelity  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Open ADR:** [ADR-057](ADR_057_STAGE26_OPEN.md)

Stage 26 closes the owner product outline after Stage 25 freeze: **Monitoring & Alerting + WAL/PITR Resilience + Kubernetes Deploy Fidelity + Load Capacity Evidence → Ops Platform Fidelity**. Stage 18 delivered MVP-lite health/metrics/structured logs, logical backup schedule, CI/prod-compose, and load smoke; Stage 23 automated logical DR drill. The four unchecked Reliability & operations gates in `PRODUCTION_READINESS.md` remain open. This track extends proven ops assets (`docs/OPS_MONITORING_MVP.md`, `/api/v1/metrics`, `k8s/`, `docs/LOAD_TEST_BASELINE.md`, `docs/DR_LOGICAL_BACKUP_RUNBOOK.md`, `docs/DEPLOYMENT_GUIDE.md`) with evidence that can honestly close or Partial-close those gates — **not** paid billing, schema-per-tenant, i18n packs, ADR-003/005, Open Banking, tax e-file, PgBouncer, vendor pen test, external LLM/Prophet, or reopening Stages 1–25.

## Product outline (owner)

```
Monitoring & Alerting
        +
WAL / PITR Resilience
        +
Kubernetes Deploy Fidelity
        +
Load Capacity Evidence
        ↓
Ops Platform Fidelity
```

## Delivery rules

1. One workstream at a time (full AC + automated tests before the next).
2. Prefer extending proven Stage 5/18/23 ops patterns (`RequestLoggingMiddleware`, health/metrics, logical DR, load harness, `k8s/` starter) — do not invent fake Grafana/K8s/WAL/load success.
3. No demo data / fake success. Alembic only when schema is required.
4. After each feature: tests → commit → push → PR update.
5. Do not reopen Stage 1–25 feature scopes. Deferred ADRs (001–006), PgBouncer, vendor pen test, and product polish stay deferred.

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **M1** | Monitoring & alerting fidelity (Prometheus scrape / alert rules / log-ship hooks) | P0 | COMPLETE |
| **W1** | WAL / PITR strategy + S3 offsite backup fidelity | P0 | PENDING |
| **K1** | Kubernetes / Helm production deploy fidelity | P0 | PENDING |
| **C1** | Certified load / capacity evidence | P0 | PENDING |
| **D1** | Spec / BR-16 / readiness / launch / deploy fidelity sync | P2 | PENDING |
| **H26x** | Stage 26 exit criteria + freeze ADR | Exit | PENDING |

## Explicitly out of this pass

- Paid billing (ADR-002); schema-per-tenant (ADR-001); i18n packs (ADR-006)
- User↔store membership (ADR-005); hard-delete with archival (ADR-003)
- Open Banking; tax e-file portals
- PgBouncer; vendor penetration test / ZAP-in-CI Top 10
- Multi-bin; FIFO/LIFO/WA; PO Kanban polish; vendor USB/serial POS drivers
- Richer WYSIWYG template designer; restore-to-new-tenant
- External LLM / Prophet / IsolationForest; PO OCR auto-apply
- Reopening Stages 1–25 frozen feature scopes (incl. Stage 18 L1/T1/C1, Stage 23 B1, Stage 25 AI as greenfield)

## M1 acceptance criteria

- [x] Prometheus scrape + alert-rule fidelity over existing `/api/v1/metrics` / health hooks (extend `OPS_MONITORING_MVP.md` — not a parallel stack).
- [x] Log-shipping / aggregation operator hooks documented against Stage 18 structured JSON logs (no fake SIEM claim).
- [x] Automated proof: `backend/tests/test_ops_monitoring_m1.py`.
- [x] PRODUCTION_READINESS monitoring gate honesty updated with evidence (Remaining only if still deferred).
- [x] Plan / launch / roadmap cite Stage 26 M1.

## W1 acceptance criteria

- [ ] WAL / PITR strategy + S3-compatible offsite packaging documented and evidence-tested (extend logical DR — not fake pg_dump success).
- [ ] Operator runbook + durable drill/config artifact path.
- [ ] Automated proof: `backend/tests/test_wal_pitr_w1.py`.
- [ ] PRODUCTION_READINESS WAL gate honesty updated with evidence.
- [ ] Plan / launch / roadmap cite Stage 26 W1.

## K1 acceptance criteria

- [ ] Kubernetes / Helm (or hardened `k8s/`) production-chart fidelity + staging deploy smoke evidence (extend Stage 18 C1 — not fake cluster claim).
- [ ] `DEPLOYMENT_GUIDE.md` / CI wiring synced to proven assets.
- [ ] Automated proof: `backend/tests/test_k8s_deploy_k1.py`.
- [ ] PRODUCTION_READINESS Kubernetes gate honesty updated with evidence.
- [ ] Plan / launch / roadmap cite Stage 26 K1.

## C1 acceptance criteria

- [ ] Capacity evidence against `docs/LOAD_TEST_BASELINE.md` targets (extend Stage 18 T1 harness — not invented 1000-VU certificate without artifact).
- [ ] Durable artifact path under `/opt/cursor/artifacts/loadtest/` (or equivalent).
- [ ] Automated proof: `backend/tests/test_load_capacity_c1.py`.
- [ ] PRODUCTION_READINESS load gate honesty updated with evidence.
- [ ] Plan / launch / roadmap cite Stage 26 C1.

## D1 acceptance criteria

- [ ] `docs/STAGE_26_FIDELITY.md` maps M1–C1 evidence → BR-16 / readiness / launch / deploy docs.
- [ ] PRODUCTION_READINESS / LAUNCH_CHECKLIST / DEVELOPMENT_ROADMAP / DEPLOYMENT_GUIDE / SECURITY_GUIDE cite Stage 26 D1.
- [ ] Automated proof: `backend/tests/test_stage26_fidelity_d1.py`.

## H26x acceptance criteria

- [ ] Exit criteria document with no CRITICAL/MISSING rows for M1–D1 / H26x — `docs/STAGE_26_EXIT_CRITERIA.md`.
- [ ] Scope freeze ADR accepted — `docs/ADR_058_STAGE26_FREEZE.md` (number reserved at close).
- [ ] LAUNCH_CHECKLIST / DEVELOPMENT_ROADMAP / PRODUCTION_READINESS cite exit + freeze.
- [ ] Automated proof: `backend/tests/test_stage26_exit_h26x.py`.
- [ ] Stages 1–25 freezes remain; Stage 27+ requires explicit open ADR after CONTINUE/NEXT.

## Sign-off

Stage 26 open under ADR-057. M1 complete; W1 next. Stages 1–25 remain frozen for their scopes.
