# Stage 12 Plan — Order-to-Cash & POS Chain Fidelity

**Status:** Closed — exit met; freeze [ADR-030](ADR_030_STAGE12_FREEZE.md)  
**Base:** Customers → Sales → Sales Items → Invoices → Payments → POS  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Exit:** [STAGE_12_EXIT_CRITERIA.md](STAGE_12_EXIT_CRITERIA.md)  
**Fidelity:** [STAGE_12_FIDELITY.md](STAGE_12_FIDELITY.md)

Stage 12 closes commercial-MVP order-to-cash and POS chain fidelity after Stage 11 freeze. It is **not** Kubernetes, WAL/PITR, vendor pen test, Open Banking, FIFO/LIFO, or USB serial drivers beyond existing bridges.

## Delivery rules

1. One workstream at a time (full AC + automated tests before the next).
2. Prefer extending proven patterns (Stage 11 PO/POS tax-on-net → sales docs; purchasing chain E2E → sales/POS chains).
3. No demo data / fake success. Alembic only when schema is required.
4. After each feature: tests → commit → push → PR update.

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **C1** | Order-to-Cash E2E + sales line tax-on-net-after-discount | P0 | COMPLETE |
| **C2** | POS chain E2E (shift → cart/discount/tax → pay → receipt → stock → close) | P0 | COMPLETE |
| **A1** | Sales/POS domain audit closeout | P1 | COMPLETE |
| **D1** | Spec / BR-7/8 / readiness / launch checklist fidelity sync | P2 | COMPLETE |
| **H12x** | Stage 12 exit criteria + freeze ADR | Exit | COMPLETE |

## Explicitly out of this pass

- Kubernetes / Helm; full Prometheus/Grafana/PagerDuty
- pg_dump / WAL / S3 offsite PITR; vendor pen test; PgBouncer
- Paid billing (ADR-002); schema-per-tenant (ADR-001); i18n (ADR-006)
- Certified 1000-VU; Prophet/LLM; multi-bin; PO Kanban
- Open Banking; tax e-file; FIFO/LIFO/WA; USB/serial POS drivers beyond existing

## C1 acceptance criteria

- [x] Quote/order/invoice line math: tax on net after line discount (`calc_sale_line_amounts`).
- [x] Automated E2E: customer → quotation → order → confirm → invoice → post → payment (stock, AR, journal, audit).
- [x] Unit coverage for discounted line totals (`test_sales_chain_c1.py`).

## C2 acceptance criteria

- [x] Automated POS chain: open → barcode search → cart (line+cart discount, tax) → cash pay → receipt → stock → journal → close/variance → report (`test_pos_chain_c2.py`).
- [x] Cart-level discount applied after line tax (documented by C2 totals: subtotal 180 + tax 27 − cart 7 = 200).

## A1 acceptance criteria

- [x] Domain audit `pos_session_opened`, `pos_sale_completed`, `pos_session_closed`; OTC `invoice_posted` / `customer_payment` already covered. Tests: `test_pos_audit_a1.py`.

## D1 acceptance criteria

- [x] BR-7/8 / readiness / launch checklist aligned — `docs/STAGE_12_FIDELITY.md`.

## H12x acceptance criteria

- [x] Exit criteria + freeze ADR-030 + `backend/tests/test_stage12_exit_h12x.py`.

## Sign-off

Stage 12 exit is met. Feature scope is frozen under ADR-030 (bugfixes / security / tests / docs only until CONTINUE opens the next track).
