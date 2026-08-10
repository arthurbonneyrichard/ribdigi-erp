# Stage 15 Plan — Sales Inventory–Ledger Chain Fidelity

**Status:** Open  
**Base:** Sales → Inventory → Customer balance → Tax → Accounting → Audit  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Open ADR:** [ADR-035](ADR_035_STAGE15_OPEN.md)

Stage 15 closes commercial-MVP fidelity on the sales→ledger path after Stage 14 freeze. OTC/POS and Credit engines already exist (Stages 12–13 / 8). This track proves invoice→stock→AR→tax→journal→audit end-to-end, adds standard-cost COGS/Inventory GL, hardens post atomicity and returns, and syncs docs — **not** Open Banking, tax e-file, FIFO/LIFO, or greenfield Sales.

## Delivery rules

1. One workstream at a time (full AC + automated tests before the next).
2. Prefer extending proven patterns (Stage 12 `test_sales_chain_c1` → deeper chain; Stage 13 POS stock preflight → invoice post; GRN Inventory `1200` ↔ sales COGS `5000`).
3. No demo data / fake success. Alembic only when schema is required.
4. After each feature: tests → commit → push → PR update.
5. Do not reopen Stage 1–14 feature scopes; do not rewrite the Credit engine (already Complete).

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **C1** | Invoice chain proof (stock movement → AR → tax report → JE lines) | P0 | PENDING |
| **I1** | Standard-cost COGS + Inventory GL on sale (/POS helper) + return reverse | P0 | PENDING |
| **H1** | Invoice post atomicity (stock preflight; no partial AR/JE) | P0 | PENDING |
| **R1** | Sales return chain fidelity (warehouse restock, AR/tax/COGS, store) | P1 | PENDING |
| **T1** | Sales-path tax → filing from live invoice post | P1 | PENDING |
| **A1** | Sales-path domain audit closeout (`sales_return_posted`, enrich `invoice_posted`) | P1 | PENDING |
| **D1** | Spec / BR-5/7/10/12/17 / readiness fidelity sync | P2 | PENDING |
| **H15x** | Stage 15 exit criteria + freeze ADR | Exit | PENDING |

## Explicitly out of this pass

- Kubernetes / Helm; Prometheus/Grafana/PagerDuty; PgBouncer
- pg_dump / WAL / S3 offsite PITR; vendor pen test; certified 1000-VU
- Paid billing (ADR-002); schema-per-tenant (ADR-001); i18n (ADR-006)
- Native Open Banking; tax authority e-file portals
- FIFO/LIFO/WA; multi-bin; PO Kanban; USB/serial POS drivers
- Rewriting Credit core; reopening Stage 12–14 frozen feature scopes

## C1 acceptance criteria

- [ ] Post sales invoice proves `stock_movements` with `reference_type=sales_invoice`, customer balance increase (base), tax report output includes the invoice, and JE lines hit AR `1100` / Revenue `4000` / Tax `2100` as applicable.
- [ ] Automated proof beyond Stage 12 qty/total-only checks: `backend/tests/test_sales_inventory_ledger_chain_c1.py`.

## I1–H15x

See workstream table; detailed ACs filled when each workstream starts.

## Sign-off

Track open under ADR-035. Pending C1 → … → H15x.
