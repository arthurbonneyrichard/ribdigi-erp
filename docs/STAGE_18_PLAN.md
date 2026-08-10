# Stage 18 Plan — Launch Integrity & Ops Fidelity

**Status:** Open  
**Base:** Security → Backup/Restore → Data integrity → Logging/Monitoring → Test & deploy hygiene  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Open ADR:** [ADR-041](ADR_041_STAGE18_OPEN.md)

Stage 18 closes commercial-MVP launch integrity after Stage 17 freeze. Security, backup, audit, health, load harness, and domain integrity engines already exist (Stages 1 / 5 / 7 / 10–17). This track proves remaining gaps with live evidence and docs sync — **not** Kubernetes, WAL/PITR, vendor pen test, or certified 1000-VU.

## Product outline (owner)

```
Security hardening
 ├── Tenant isolation
 ├── RBAC
 ├── Session security
 └── Audit logs

Backup
 └── Restore

Database integrity
 ├── Inventory reconciliation
 ├── Accounting reconciliation
 └── POS transaction integrity

Error handling
 ├── Logging
 └── Monitoring

Performance testing
 ├── Security testing
 ├── End-to-end testing
 ├── Deployment configuration
 ├── CI/CD
 └── Production configuration
```

## Delivery rules

1. One workstream at a time (full AC + automated tests before the next).
2. Prefer extending proven Stage 1/5/7 patterns (isolation matrix, audit, backup B1, OWASP O1, health H5, load L1, launch L7x) and Stage 11–17 integrity chains.
3. No demo data / fake success. Alembic only when schema is required.
4. After each feature: tests → commit → push → PR update.
5. Do not reopen Stage 1–17 feature scopes; do not rewrite security/backup engines.

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **S1** | Tenant isolation matrix completeness (MVP write/read paths) | P0 | COMPLETE |
| **A1** | Security hardening fidelity (RBAC / session / audit BR-17 sync + sensitive-path proof) | P0 | COMPLETE |
| **B1** | Backup schedule / retention / failure notify + restore drill evidence | P0 | COMPLETE |
| **I1** | Cross-module integrity (inventory Σ movements · accounting TB/GL · POS money-path) | P0 | COMPLETE |
| **L1** | Structured request/error logging + health/metrics monitoring hooks (MVP-lite) | P0 | COMPLETE |
| **T1** | Testing fidelity (OWASP expand · load evidence · launch E2E smoke) | P0 | COMPLETE |
| **C1** | CI + production configuration fidelity (no K8s deploy) | P1 | PENDING |
| **D1** | Spec / BR-16–17 / readiness / launch fidelity sync | P2 | PENDING |
| **H18x** | Stage 18 exit criteria + freeze ADR | Exit | PENDING |

## Explicitly out of this pass

- Kubernetes / Helm production chart review; GHA → staging K8s deploy
- Full Prometheus / Grafana / PagerDuty stack
- pg_dump / WAL / S3 offsite PITR (logical `.ribbak` archive to S3-compatible store may land under B1 if needed; PITR stays deferred)
- PgBouncer; certified ~1000-VU capacity certificate
- Vendor penetration test / ZAP-in-CI full Top 10
- Paid billing (ADR-002); schema-per-tenant (ADR-001); i18n packs (ADR-006)
- User↔store membership (ADR-005); multi-bin; FIFO/LIFO/WA
- WebSocket realtime notifications; Open Banking; tax e-file portals
- Prophet/LLM upgrades; PO Kanban polish
- Reopening Stage 1–17 frozen feature scopes

## S1 acceptance criteria

- [x] Isolation matrix covers MVP tenant-owned resources used in launch smoke (foreign-id / header-mismatch proofs); no schema-per-tenant.
- [x] Automated proof: `backend/tests/test_isolation_matrix_s1.py` (extends `test_tenant_isolation_matrix.py` for API keys, webhooks, OCR-apply, stock counts, warehouse transfers, quotations/orders, product surfaces).

## A1 acceptance criteria

- [x] RBAC / session / audit paths proven against BR-17 where engines already exist; sensitive ops still hash-chained; BR checkbox drift closed only with evidence.
- [x] Automated proof: `backend/tests/test_security_hardening_a1.py`.

## B1 acceptance criteria

- [x] Backup schedule (daily/weekly) + retention prune proven; failure surfaces an admin notification (no fake success); restore dry-run / verify path remains green; DR drill evidence path documented (`docs/DR_LOGICAL_BACKUP_RUNBOOK.md`).
- [x] Automated proof: `backend/tests/test_backup_schedule_b1.py` (plus existing `test_backup_restore_proof_b1.py`).

## I1 acceptance criteria

- [x] Inventory qty = Σ movements (incl. Stage 17 chains); accounting journals/TB balanced with Inventory GL / AR-AP sanity; POS sale paths leave no orphan sale/payment/JE/stock.
- [x] Automated proof: `backend/tests/test_cross_module_integrity_i1.py` (extends Stage 2/13/15 recon and atomicity patterns).

## L1 acceptance criteria

- [x] Structured JSON request/error logs (request_id, tenant_id, user_id, status, latency, safe error codes); health/ready + `/metrics` monitoring hooks documented/tested (MVP-lite — not Grafana/PagerDuty). Docs: `docs/OPS_MONITORING_MVP.md`.
- [x] Automated proof: `backend/tests/test_request_logging_l1.py` (health/metrics remain covered by `test_health_metrics_h5.py`).

## T1 acceptance criteria

- [x] OWASP suite extended for Stage 6–17 surfaces; load-test baseline evidence artifact path; launch checklist §4 rows automated where feasible (expense→JE, TB, backup verify/dry-run).
- [x] Automated proof: `test_owasp_suite_t1.py`, `test_loadtest_evidence_t1.py`, `test_launch_smoke_t1.py` (evidence under `/opt/cursor/artifacts/loadtest/`).

## C1 acceptance criteria

- [ ] CI runs pytest (+ security/isolation markers as applicable) and frontend build; production Compose/env template aligned with Stage 5 S1 validators (Redis-required rate limit, CORS, secrets posture). No K8s deploy job.
- [ ] Automated / doc proof.

## D1 acceptance criteria

- [ ] BR-16/17, SECURITY_GUIDE, readiness, launch checklist aligned — `docs/STAGE_18_FIDELITY.md`.
- [ ] Guard test: `backend/tests/test_stage18_fidelity_d1.py`.

## H18x acceptance criteria

See workstream table; filled when exit workstream starts.

## Sign-off

S1–A1–B1–I1–L1–T1 complete. Pending C1 → D1 → H18x. Stages 1–17 remain frozen for their scopes.
