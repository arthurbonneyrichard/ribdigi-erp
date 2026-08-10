# Stage 14 Plan — Finance Closeout Chain Fidelity

**Status:** Closed — exit met; freeze [ADR-034](ADR_034_STAGE14_FREEZE.md)  
**Base:** Expenses → Accounting (COA, JE, GL, TB, P&L, Cash Flow) → Credit → Tax  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Exit:** [STAGE_14_EXIT_CRITERIA.md](STAGE_14_EXIT_CRITERIA.md)  
**Fidelity:** [STAGE_14_FIDELITY.md](STAGE_14_FIDELITY.md)  
**Open ADR (historical):** [ADR-033](ADR_033_STAGE14_OPEN.md)

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
| **E2** | Expense org dimensions (department + store UI) | P0 | COMPLETE |
| **A1** | Dimensional journals + store-filtered P&L/cash-flow | P0 | COMPLETE |
| **A2** | Point-in-time trial balance / balance sheet `as_of` | P0 | COMPLETE |
| **T1** | Tax rate lifecycle (edit/deactivate) + report period helpers | P1 | COMPLETE |
| **R1** | Credit UI: allocate payment to selected invoice/bill | P1 | COMPLETE |
| **A3** | Finance domain audit closeout (expense approve/reject) | P1 | COMPLETE |
| **D1** | Spec / BR-9/10/12 / readiness fidelity sync | P2 | COMPLETE |
| **H14x** | Stage 14 exit criteria + freeze ADR | Exit | COMPLETE |

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

## E2 acceptance criteria

- [x] `expenses.department_id` + `recurring_expenses.store_id` / `department_id` (Alembic).
- [x] Create/update expense accepts store/department with tenant-scoped 404; list filters `store_id` / `department_id`.
- [x] Recurring templates carry org dims into generated expenses.
- [x] Expenses UI: store/department pickers, filters, table columns.
- [x] Tests: `backend/tests/test_expense_org_dimensions_e2.py`.

## A1 acceptance criteria

- [x] `journal_entries.store_id` (nullable FK → `stores.id`); Alembic migration.
- [x] Auto-post from expense / sales invoice / POS sets store when known; manual create accepts `store_id` (tenant-scoped 404).
- [x] `GET` journal-entries, accounting/reports P&L, and cash-flow filter by `store_id`.
- [x] Accounting UI: store on manual post, P&L filter, journal list filter + column; Reports UI passes store for P&L/cash-flow.
- [x] Automated proof: `backend/tests/test_journal_store_dimension_a1.py`.

## A2 acceptance criteria

- [x] `GET /accounting/trial-balance` and `/reports/trial-balance` accept `as_of_date`; balances from posted journals through that date (live balances when omitted).
- [x] `GET /reports/balance-sheet` accepts `as_of_date` with the same semantics; response includes `as_of`.
- [x] Report export passes `as_of_date` for trial balance / balance sheet.
- [x] Accounting UI: trial balance as-of date; Reports UI: balance sheet uses To date as as-of.
- [x] Automated proof: `backend/tests/test_trial_balance_as_of_a2.py`.

## T1 acceptance criteria

- [x] `TaxUpdate` + `PATCH /tax/rates/{id}` edit name/rate/type/mode/components/flags; deactivate clears default.
- [x] `GET /tax/rates?active_only=` filter; resolve paths already skip inactive rates.
- [x] Period helpers: `quarter_bounds` / `year_bounds` / `resolve_report_period` wired to tax report + filing (`period=monthly|quarterly|annually`).
- [x] Tax UI: edit/deactivate, month/quarter/year presets.
- [x] Automated proof: `backend/tests/test_tax_rate_lifecycle_t1.py`.

## R1 acceptance criteria

- [x] Credit UI: allocate payment to selected open AR invoice or AP bill/PO (or Auto oldest-first).
- [x] Pay payload sends `sales_invoice_id` / `purchase_invoice_id` / `purchase_order_id` when selected; omit for auto-allocate.
- [x] Outstanding table row action selects document + fills amount.
- [x] Automated proof: `backend/tests/test_credit_payment_allocate_r1.py` (explicit vs auto for AR and AP).

## A3 acceptance criteria

- [x] Domain audit events: `expense_submitted`, `expense_auto_approved`, `expense_level_approved`, `expense_approved`, `expense_rejected` (`module=expenses`).
- [x] Emitted from expense service (create/approve/reject/edit auto-approve), with integrity hash.
- [x] Final/auto approve still yields `journal_posted` with `source_type=expense`.
- [x] Automated proof: `backend/tests/test_expense_audit_a3.py`.

## D1 acceptance criteria

- [x] BR-9/10/11/12, API §§9–12, DB, security, readiness, user manual, launch checklist aligned — `docs/STAGE_14_FIDELITY.md`.
- [x] Guard test: `backend/tests/test_stage14_fidelity_d1.py`.

## H14x acceptance criteria

- [x] `docs/STAGE_14_EXIT_CRITERIA.md` records E1–E2, A1–A3, T1, R1, D1, H14x COMPLETE with evidence.
- [x] Scope freeze ADR-034 accepted; automated guard test `backend/tests/test_stage14_exit_h14x.py`.

## Sign-off

Stage 14 exit is met. Feature scope is frozen under ADR-034 (bugfixes / security / tests / docs only until CONTINUE opens the next track).
