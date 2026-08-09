# Stage 9 Plan — Report Fidelity & Document Attachments Closeout

**Status:** Closed (exit met — ADR-024)  
**Base:** BR-10.2 / reporting + document fidelity after Stage 8 freeze  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Exit:** [STAGE_9_EXIT_CRITERIA.md](STAGE_9_EXIT_CRITERIA.md)

Stage 9 closes commercial-MVP holes for journal supporting documents, purchase/stock report depth, and documentation fidelity. It is **not** Kubernetes, WAL/PITR, vendor pen test, FIFO/LIFO, or paid billing.

## Delivery rules

1. One workstream at a time (full AC + automated tests before the next).
2. Prefer extending proven patterns (expense/purchase-invoice attachments → journal attachments; existing reports → deeper purchase/stock reports).
3. No demo data / fake success. Alembic only when schema is required.
4. After each feature: tests → commit → push → PR update.

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **J1** | Journal supporting documents (upload/download/delete + Ledger UI) | P0 | COMPLETE |
| **R1** | Purchase report depth: pending POs + purchase-return summary | P1 | COMPLETE |
| **R2** | Stock valuation report (qty × cost_price; no FIFO/LIFO) | P1 | COMPLETE |
| **D1** | Spec / API / User Manual fidelity sync | P2 | COMPLETE |
| **H9x** | Stage 9 exit criteria + freeze ADR | Exit | COMPLETE |

## Explicitly out of this pass

- Kubernetes / Helm production chart review
- Full Prometheus/Grafana/PagerDuty stack
- pg_dump / WAL / S3 offsite PITR
- Vendor penetration test / ZAP-in-CI full Top 10
- Paid billing (ADR-002); schema-per-tenant (ADR-001); i18n packs (ADR-006)
- Certified 1000-VU staging run; Prophet/LLM; multi-bin; PgBouncer
- PO Kanban (Stage 2 P2); Open Banking; tax e-file
- FIFO / LIFO / moving-average inventory costing beyond qty × `cost_price`

## J1 acceptance criteria

- [x] `journal_entries.attachment_url` column via Alembic; serialized as `attachment_url` + `has_attachment`.
- [x] `POST/GET/DELETE /accounting/journal-entries/{id}/attachment` with `accounting` write/read RBAC, tenant scope, and record-scope on `created_by`.
- [x] Accounting Ledger UI: upload / download / remove supporting document on recent journals.
- [x] Automated tests in `backend/tests/test_journal_attachments_j1.py`.

## R1 acceptance criteria

- [x] Purchase reports expose pending purchase orders and a purchase-return summary (tenant-scoped + reports RBAC).
- [x] UI or existing Reports surface shows the new sections.
- [x] Automated tests cover the new report payloads (`backend/tests/test_purchase_report_depth_r1.py`).

## R2 acceptance criteria

- [x] Stock valuation report returns quantity × `cost_price` (and totals), warehouse/store filter where applicable.
- [x] No FIFO/LIFO claims; docs state costing method clearly.
- [x] Automated tests cover valuation math and RBAC/tenant isolation (`backend/tests/test_stock_valuation_r2.py`).

## D1 acceptance criteria

- [x] BR / API / User Manual / DATABASE docs updated for Stage 9 delivered behavior.
- [x] Checkbox / status language matches implementation (no false COMPLETE).
- [x] Fidelity note `docs/STAGE_9_FIDELITY.md` + guard `backend/tests/test_stage9_fidelity_d1.py`.

## H9x acceptance criteria

- [x] `docs/STAGE_9_EXIT_CRITERIA.md` records J1/R1/R2/D1/H9x COMPLETE with evidence.
- [x] Scope freeze ADR-024 accepted; automated guard in `backend/tests/test_stage9_exit_h9x.py`.

## Sign-off

Stage 9 exit is recorded in `docs/STAGE_9_EXIT_CRITERIA.md` with freeze [ADR-024](ADR_024_STAGE9_FREEZE.md).
