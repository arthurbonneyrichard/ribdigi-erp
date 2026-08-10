# Stage 13 Plan — POS Sale Execution Chain Hardening

**Status:** Open  
**Base:** POS → Sale → Payment → Inventory deduction → Receipt → Accounting → Audit  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Open ADR:** [ADR-031](ADR_031_STAGE13_OPEN.md)

Stage 13 hardens the POS sale execution path after Stage 12 freeze. Stage 12 already proved cash-path E2E and session/sale audits. This track closes atomicity, multi-tender closeout, and receipt-send proof — **not** greenfield POS, USB/serial drivers, Open Banking, or FIFO/LIFO.

## Delivery rules

1. One workstream at a time (full AC + automated tests before the next).
2. Prefer extending proven patterns (Stage 12 POS chain → atomicity/multi-tender; inventory `INSUFFICIENT_STOCK` → POS preflight).
3. No demo data / fake success. Alembic only when schema is required.
4. After each feature: tests → commit → push → PR update.

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **H1** | Atomic sale integrity (stock-fail → no orphans; success → stock + JE + audit) | P0 | COMPLETE |
| **H2** | Multi-tender + receipt send + drawer on cash portion | P0 | COMPLETE |
| **D1** | Spec / BR-8 / readiness fidelity sync for POS execution chain | P2 | COMPLETE |
| **H13x** | Stage 13 exit criteria + freeze ADR | Exit | PENDING |

## Explicitly out of this pass

- Kubernetes / Helm; full Prometheus/Grafana/PagerDuty
- pg_dump / WAL / S3 offsite PITR; vendor pen test; PgBouncer
- Paid billing (ADR-002); schema-per-tenant (ADR-001); i18n (ADR-006)
- Certified 1000-VU; Prophet/LLM; multi-bin; PO Kanban
- Open Banking; tax e-file; FIFO/LIFO/WA; USB/serial POS drivers beyond existing
- Reopening Stage 9–12 feature scope

## H1 acceptance criteria

- [x] Insufficient stock on `POST /pos/sales` → 409 `INSUFFICIENT_STOCK` (or structured equivalent); no committed `Transaction`, `PosPayment`, or `pos_sale` journal; session totals unchanged.
- [x] Success path still commits payment → stock out → `pos_sale` journal linked to sale id → `pos_sale_completed` audit in one commit.
- [x] Fail-fast stock preflight before creating the sale transaction (aggregated line qty).
- [x] Automated proof: `backend/tests/test_pos_sale_atomicity_h1.py`.

## H2 acceptance criteria

- [x] One E2E: open session → multi-tender (cash + non-cash) → stock → receipt → journal → close.
- [x] Receipt send happy path with domain audit (`pos_receipt_sent`).
- [x] Drawer pulse when split includes a cash portion (`has_cash_tender`); no pulse without cash.

## D1 acceptance criteria

- [x] BR-8 / API / readiness / launch checklist aligned — `docs/STAGE_13_FIDELITY.md`.
- [x] Guard test: `backend/tests/test_stage13_fidelity_d1.py`.

## H13x acceptance criteria

- [ ] `docs/STAGE_13_EXIT_CRITERIA.md` + freeze ADR; automated guard test.

## Sign-off

H1, H2, and D1 complete. Pending H13x exit + freeze.
