# Stage 23 Plan — Reports Dimension & Commercial MVP Gate Fidelity

**Status:** Closed — exit met (H23x / ADR-052)  
**Base:** Reports dimension → Commercial MVP gate closure → Fidelity closeout  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Open ADR (historical):** [ADR-051](ADR_051_STAGE23_OPEN.md)  
**Exit:** [STAGE_23_EXIT_CRITERIA.md](STAGE_23_EXIT_CRITERIA.md) · [ADR-052](ADR_052_STAGE23_FREEZE.md) · [STAGE_23_FIDELITY.md](STAGE_23_FIDELITY.md)

Stage 23 closes remaining commercial-MVP report-dimension and readiness-gate fidelity after Stage 22 freeze. Financial reports, isolation matrix, and logical backup engines already exist (Stages 5 / 14 / 16 / 18 / 21 / 22). This track proves BR-14.5 filter/comparative residuals, readiness honesty, and logical DR drill evidence — **not** paid billing, schema-per-tenant, i18n packs, Open Banking, tax e-file portals, K8s/WAL/PITR, Grafana, certified 1000-VU, ADR-003/005, or reopening Stages 1–22.

## Product outline (owner)

```
Reports dimension fidelity
 ├── Balance sheet store · branch filters (BR-14.5)
 ├── Financial report filter parity (date / store / branch)
 └── Financial comparative P&L · cash-flow · BS (BR-14.5 residual)

Commercial MVP gate closure
 ├── Isolation matrix residual coverage
 ├── Module Partial→Complete honesty where Remaining = deferred-only
 └── Logical DR drill automation evidence (no WAL/PITR)

Fidelity closeout
 ├── Docs / BR-14 / readiness / USER_MANUAL / launch sync
 └── Exit + freeze
```

## Delivery rules

1. One workstream at a time (full AC + automated tests before the next).
2. Prefer extending proven reports / accounting / backup engines — do not rewrite stacks or invent fake success.
3. No demo data / fake success. Alembic only when schema is required.
4. After each feature: tests → commit → push → PR update.
5. Do not reopen Stage 1–22 feature scopes. Deferred ADRs (001–006) and ops platforms stay deferred.

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **F1** | Balance sheet + financial dimension filters (BR-14.5) | P0 | COMPLETE |
| **C1** | Financial comparative fidelity (P&L / cash-flow / BS) | P0 | COMPLETE |
| **I1** | Isolation matrix residual coverage | P1 | COMPLETE |
| **G1** | Commercial MVP gate closure (readiness honesty) | P1 | COMPLETE |
| **B1** | Logical DR drill automation evidence | P1 | COMPLETE |
| **D1** | Spec / BR-14 / readiness / USER_MANUAL / API fidelity sync | P2 | COMPLETE |
| **H23x** | Stage 23 exit criteria + freeze ADR | Exit | COMPLETE |

## Explicitly out of this pass

- Paid billing (ADR-002); schema-per-tenant (ADR-001); i18n packs (ADR-006)
- User↔store membership (ADR-005); hard-delete with archival (ADR-003)
- Open Banking; tax e-file portals
- Kubernetes / Helm; Grafana / PagerDuty / SIEM
- pg_dump / WAL / S3 offsite PITR; PgBouncer
- Certified ~1000-VU; vendor penetration test / ZAP-in-CI Top 10
- Multi-bin; FIFO/LIFO/WA; PO Kanban polish
- WebSocket realtime; external LLM / Prophet; PO OCR auto-apply
- Richer WYSIWYG template designer; restore-to-new-tenant
- Reopening Stages 1–22 frozen feature scopes

## F1 acceptance criteria

- [x] `GET /reports/balance-sheet` accepts `store_id` and `branch_id` (journal dimension; foreign → 404).
- [x] `as_of_date` remains correct under those filters; empty branch (no stores) returns zeroed balanced sheet.
- [x] P&L and cash-flow accept `branch_id` for filter parity with store.
- [x] Reports UI exposes store/branch filters on Balance Sheet / P&L / Cash flow.
- [x] Automated proof: `backend/tests/test_financial_report_filters_f1.py`.
- [x] BR-14.5 filter AC synced with Stage 23 F1 evidence.

## C1 acceptance criteria

- [x] `compare=true` on P&L / cash-flow returns equal-length prior-period metrics + `change_pct`.
- [x] `compare=true` on balance sheet returns prior month-end `as_of` metrics + `change_pct`.
- [x] Reports UI requests compare and surfaces prior / change on financial tabs.
- [x] Export includes comparison metrics when `compare=true`.
- [x] Automated proof: `backend/tests/test_financial_comparative_c1.py`.
- [x] BR-14.5 comparative AC synced (no longer deferred).

## I1 acceptance criteria

- [x] Foreign liquid accounts / transfers → 404; list excludes other-tenant codes.
- [x] Foreign expense categories / recurring → 404; lists exclude foreign ids.
- [x] Foreign branch + report `store_id`/`branch_id` on BS/P&L/cash-flow → 404.
- [x] Mismatched `X-Tenant-ID` on financial reports / liquid accounts / expense budgets → 403.
- [x] Automated proof: `backend/tests/test_isolation_matrix_i1.py`.
- [x] PRODUCTION_READINESS / SECURITY_GUIDE / launch synced (schema-per-tenant remains deferred ADR-001).

## G1 acceptance criteria

- [x] Cross-tenant isolation + tenant lifecycle gates marked Complete (MVP) with Remaining limited to ADR-001 / ADR-002 / WYSIWYG.
- [x] Expenses / Accounting / Tax / Reports gates marked Complete (MVP); Remaining only Open Banking, tax e-file, extra jurisdictions / FIFO-LIFO-WA.
- [x] No fake-complete of still-Partial inventory/sales/purchasing/POS/multi-store or ops WAL/PITR/monitoring/K8s/load/DR drill.
- [x] Automated proof: `backend/tests/test_mvp_gate_closure_g1.py`.
- [x] LAUNCH_CHECKLIST / DEVELOPMENT_ROADMAP / plan synced (Stage 23 G1).

## B1 acceptance criteria

- [x] Automated logical DR drill: create → corrupt → dry-run → blocked bad confirm → apply `RESTORE` → verify proof + audits.
- [x] Foreign-tenant backup restore / verify / download → 404 (no cross-tenant restore).
- [x] Durable evidence artifact `/opt/cursor/artifacts/dr/stage23_b1_logical_drill.json`.
- [x] PRODUCTION_READINESS Disaster recovery drill gate Complete (MVP); Remaining WAL/PITR only.
- [x] Automated proof: `backend/tests/test_logical_dr_drill_b1.py`.
- [x] Runbook / launch / roadmap synced (Stage 23 B1).

## D1 acceptance criteria

- [x] `docs/STAGE_23_FIDELITY.md` maps F1–B1 evidence → BR-14 / readiness / DR gates and deferred items.
- [x] BR-14.5 + BR-16.3 fidelity cites include Stage 23 D1 / `STAGE_23_FIDELITY.md`.
- [x] USER_MANUAL §§8.6 / 12 financial filters/compare + Settings backup/DR synced.
- [x] API docs financial reports + Backup & Logical Restore + Stage 23 D1 cite.
- [x] PRODUCTION_READINESS / LAUNCH_CHECKLIST / DEVELOPMENT_ROADMAP cite Stage 23 D1.
- [x] Automated proof: `backend/tests/test_stage23_fidelity_d1.py`.

## H23x acceptance criteria

- [x] Exit criteria document with no CRITICAL/MISSING rows for F1–D1 / H23x — `docs/STAGE_23_EXIT_CRITERIA.md`.
- [x] Scope freeze ADR accepted — `docs/ADR_052_STAGE23_FREEZE.md`.
- [x] Fidelity note closed with H23x evidence — `docs/STAGE_23_FIDELITY.md`.
- [x] LAUNCH_CHECKLIST / DEVELOPMENT_ROADMAP / PRODUCTION_READINESS / API cite exit + freeze.
- [x] Automated proof: `backend/tests/test_stage23_exit_h23x.py`.
- [x] Stages 1–22 freezes remain; Stage 24+ requires explicit open ADR after CONTINUE/NEXT.

## Sign-off

Stage 23 exit met (F1–D1 / H23x). Scope frozen under ADR-052. Stages 1–22 remain frozen for their scopes. Next delivery track requires an explicit open ADR after CONTINUE/NEXT.
