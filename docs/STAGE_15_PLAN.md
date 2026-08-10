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
| **C1** | Invoice chain proof (stock movement → AR → tax report → JE lines) | P0 | COMPLETE |
| **I1** | Standard-cost COGS + Inventory GL on sale (/POS helper) + return reverse | P0 | COMPLETE |
| **H1** | Invoice post atomicity (stock preflight; no partial AR/JE) | P0 | COMPLETE |
| **R1** | Sales return chain fidelity (warehouse restock, AR/tax/COGS, store) | P1 | COMPLETE |
| **T1** | Sales-path tax → filing from live invoice post | P1 | COMPLETE |
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

- [x] Post sales invoice proves `stock_movements` with `reference_type=sales_invoice`, customer balance increase (base), tax report output includes the invoice, and JE lines hit AR `1100` / Revenue `4000` / Tax `2100` as applicable.
- [x] Automated proof beyond Stage 12 qty/total-only checks: `backend/tests/test_sales_inventory_ledger_chain_c1.py`.

## I1 acceptance criteria

- [x] `post_sales_invoice_journal` (and shared POS helper path) posts Dr COGS `5000` / Cr Inventory `1200` at qty × standard `cost_price` when cost > 0.
- [x] Sales return reverse restores Inventory and credits COGS for restocked sellable lines.
- [x] Zero cost skips COGS/Inventory lines; P&L `cogs` reflects posted COGS.
- [x] Automated proof: `backend/tests/test_sales_cogs_inventory_i1.py`.

## H1 acceptance criteria

- [x] Insufficient stock on invoice post → structured 409 `INSUFFICIENT_STOCK`; no AR bump, no JE, invoice stays draft, no partial stock movements.
- [x] Aggregated multi-line preflight (same product lines cannot bypass line-by-line).
- [x] Success path still commits stock + AR + journal.
- [x] Automated proof: `backend/tests/test_sales_invoice_atomicity_h1.py`.

## R1 acceptance criteria

- [x] Restock to invoice store warehouse (`warehouse_id` on stock_in movements).
- [x] Customer AR credit uses `to_base` via invoice `exchange_rate`; invoice `paid_amount` stays in doc currency.
- [x] Return journal: tax reverse `2100`, COGS reverse, `store_id` from invoice; credit note allocated.
- [x] Automated proof: `backend/tests/test_sales_return_chain_r1.py`.

## T1 acceptance criteria

- [x] HTTP-posted invoice (incl. reverse-charge memo when applicable) feeds `/reports/tax` and filing boxes — not planted DB rows only.
- [x] Live posts prove standard output tax, RC box 2a, supply splits (standard/zero/exempt), and schedule document ids.
- [x] Automated proof: `backend/tests/test_sales_tax_filing_t1.py`.

## A1 acceptance criteria

- [ ] Emit `sales_return_posted`; enrich `invoice_posted` (stock/tax/AR); keep `journal_posted` linkage.
- [ ] Automated proof: `backend/tests/test_sales_audit_a1.py`.

## D1–H15x

See workstream table; detailed ACs filled when each workstream starts.

## Sign-off

C1, I1, H1, R1, and T1 complete. Pending A1 → D1 → H15x.
