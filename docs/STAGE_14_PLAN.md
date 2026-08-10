# Stage 14 Plan — Finance Closeout Chain Fidelity

**Status:** Open  
**Base:** Expenses → Accounting (COA, JE, GL, TB, P&L, Cash Flow) → Credit → Tax  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Open ADR:** [ADR-033](ADR_033_STAGE14_OPEN.md)

Stage 14 closes commercial-MVP finance fidelity after Stage 13 freeze. Engines for expenses, accounting, credit, and tax already exist (Stages 3/8/10). This track proves the expense→GL→statements chain, closes remaining BR-9/10/12 holes, and syncs docs — **not** Open Banking, tax e-file, or greenfield COA.

## Delivery rules

1. One workstream at a time (full AC + automated tests before the next).
2. Prefer extending proven patterns (`post_expense_journal`, Stage 10 category tax FK → expense category GL).
3. No demo data / fake success. Alembic only when schema is required.
4. After each feature: tests → commit → push → PR update.
5. Do not reopen Stage 1–13 feature scopes; do not rewrite the Credit engine (already Complete).

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **E1** | Category → COA posting + expense→approve→journal→TB/P&L/cash-flow E2E | P0 | COMPLETE |
| **E2** | Expense org dimensions (department + store UI) | P0 | PENDING |
| **A1** | Dimensional journals + store-filtered P&L/cash-flow | P0 | PENDING |
| **A2** | Point-in-time trial balance / balance sheet `as_of` | P0 | PENDING |
| **T1** | Tax rate lifecycle (edit/deactivate) + report period helpers | P1 | PENDING |
| **R1** | Credit UI: allocate payment to selected invoice/bill | P1 | PENDING |
| **A3** | Finance domain audit closeout (expense approve/reject) | P1 | PENDING |
| **D1** | Spec / BR-9/10/12 / readiness fidelity sync | P2 | PENDING |
| **H14x** | Stage 14 exit criteria + freeze ADR | Exit | PENDING |

## Explicitly out of this pass

- Kubernetes / Helm; Prometheus/Grafana/PagerDuty; PgBouncer
- pg_dump / WAL / S3 offsite PITR; vendor pen test; certified 1000-VU
- Paid billing (ADR-002); schema-per-tenant (ADR-001); i18n (ADR-006)
- Native Open Banking; tax authority e-file portals
- FIFO/LIFO/WA; multi-bin; PO Kanban; USB/serial POS drivers
- Rewriting Credit core beyond R1 UI polish
- Reopening Stage 1–13 frozen feature scopes

## E1 acceptance criteria

- [x] `expense_categories.account_id` (nullable FK → `accounts.id`); Alembic migration.
- [x] Create/update category accepts `account_id` (must be tenant expense-type account); serialize includes `account_id` (+ optional code/name).
- [x] `post_expense_journal` debits mapped category account; fallback `6000` when unset/invalid.
- [x] Expenses UI: pick GL account on category create/edit.
- [x] Automated E2E: custom expense COA → category link → expense approve → journal lines → TB / P&L opex / cash-flow operating (`test_expense_coa_chain_e1.py`).

## E2–H14x

See workstream table; detailed ACs filled when each workstream starts.

## Sign-off

E1 complete. Pending E2 → A1 → A2 → T1 → R1 → A3 → D1 → H14x.
