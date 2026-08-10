# Stage 12 Plan — Order-to-Cash & POS Chain Fidelity

**Status:** Open  
**Base:** Customers → Sales → Sales Items → Invoices → Payments → POS  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Exit:** `docs/STAGE_12_EXIT_CRITERIA.md` (at close)

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
| **C2** | POS chain E2E (shift → cart/discount/tax → pay → receipt → stock → close) | P0 | PENDING |
| **A1** | Sales/POS domain audit closeout | P1 | PENDING |
| **D1** | Spec / BR-7/8 / readiness / launch checklist fidelity sync | P2 | PENDING |
| **H12x** | Stage 12 exit criteria + freeze ADR | Exit | PENDING |

## Explicitly out of this pass

- Kubernetes / Helm; full Prometheus/Grafana/PagerDuty
- pg_dump / WAL / S3 offsite PITR; vendor pen test; PgBouncer
- Paid billing (ADR-002); schema-per-tenant (ADR-001); i18n (ADR-006)
- Certified 1000-VU; Prophet/LLM; multi-bin; PO Kanban
- Open Banking; tax e-file; FIFO/LIFO/WA; USB/serial POS drivers beyond existing

## C1 acceptance criteria

- [ ] Quote/order/invoice line math: tax on net after line discount (`calc_sale_line_amounts`).
- [ ] Automated E2E: customer → quotation → order → confirm → invoice → post → payment (stock, AR, journal, audit).
- [ ] Unit coverage for discounted line totals.

## C2 acceptance criteria

- [ ] Automated POS chain: open shift → cart (discount/tax) → pay → receipt → stock → close/variance.
- [ ] Cart-level discount behavior documented/tested vs line tax.

## A1 acceptance criteria

- [ ] Domain audit assertions for sales/POS money-moving steps; gaps closed where missing.

## D1 acceptance criteria

- [ ] BR-7/8 / API / readiness / launch checklist aligned with C1–A1 evidence.

## H12x acceptance criteria

- [ ] Exit criteria + freeze ADR + automated guard test.

## Sign-off

Stage 12 remains open until H12x exit criteria and freeze ADR are recorded.
