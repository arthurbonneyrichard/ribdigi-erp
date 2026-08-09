# Stage 3 Plan — Sales, POS & Financials Hardening

**Status:** Open (ADR-011)  
**Base:** Phase 3 roadmap (`docs/DEVELOPMENT_ROADMAP.md` §4) + BR-7.x–BR-11.x  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  

Stage 3 here is **not** a rewrite of sales/POS/accounting. Core engines (customers, quote→order→invoice, POS sessions, expenses, COA defaults, journals, AR/AP, tax filing packs) already exist. This plan closes remaining BR acceptance holes and UX gaps, then freezes Stage 3.

## Delivery rules

1. One workstream at a time (full AC + automated tests before the next).
2. Prefer extending proven patterns (`post_journal_entry`, liquid accounts, POS settle, credit limit checks).
3. No demo data / fake success. Alembic for any schema change.
4. After each feature: tests → commit → push → PR update.

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **A1** | Journal unpost + open fiscal-period gate (BR-10.2) | P0 | COMPLETE |
| **A2** | COA CRUD / hierarchy / opening balances (BR-10.1) | P0 | COMPLETE |
| **A3** | Financial report depth (P&L date range; cash-flow O/I/F) | P0 | COMPLETE |
| **P1** | POS split tender (`pos_payments`) | P0 | PENDING |
| **C1** | Credit-limit override with audit | P0 | PENDING |
| **H3** | Stage 3 exit criteria + freeze ADR | Exit | PENDING |

## Explicitly out of this pass

- Paid billing provider (ADR-002)
- Multi-language packs (ADR-006)
- Schema-per-tenant (ADR-001)
- Native Open Banking / Plaid adapters
- Tax authority e-file portal submission
- Vendor-specific USB/serial POS drivers beyond TCP ESC/POS / browser bridge

## A1 acceptance criteria

- [x] `POST /accounting/journal-entries/{id}/unpost` reverses account balances and sets status `unposted`.
- [x] Unpost allowed only when `entry_date` falls in the tenant’s **open** fiscal year (`tenants.fiscal_year_start` MM-DD); otherwise 409.
- [x] Reject unpost if already unposted, or if any line is bank-reconciled (matched / clearing group).
- [x] `GET /accounting/journal-entries/{id}` returns a single entry (tenant-scoped).
- [x] Accounting Ledger UI: Unpost action for eligible posted journals.
- [x] Tenant + RBAC (`accounting` write); automated tests in `backend/tests/test_journal_unpost_a1.py`.

## A2 acceptance criteria

- [x] Non-system account create/edit (`POST/PATCH /accounting/accounts`); system accounts blocked for name/code/type.
- [x] Hierarchy via `parent_id` (same `account_type`, cycle-safe); `GET .../accounts?tree=true`.
- [x] Opening balance `POST /accounting/accounts/{id}/opening-balance` posts balanced journal vs 3900 Opening Balances Equity.
- [x] Seeded equity accounts 3000/3900; `is_system` / `is_active` (Alembic `0075`).
- [x] Accounting Ledger UI: create account + opening balance + indented COA.
- [x] Tenant + RBAC (`accounting` write); automated tests in `backend/tests/test_coa_crud_a2.py`.

## A3 acceptance criteria

- [x] P&L from posted journal lines with `from_date`/`to_date` on `/accounting/profit-loss` and `/reports/profit-loss`.
- [x] P&L buckets: revenue, COGS, gross profit, operating expenses, other income, net profit.
- [x] Cash-flow splits operating / investing / financing (+ transfers for cash↔bank); opening/closing cash; `net_change` excludes transfers.
- [x] Export `profit_loss` / `cash_flow` honor date filters; Reports UI P&L tab + O/I/F cash-flow display; Ledger P&L date filter.
- [x] Automated tests in `backend/tests/test_financial_reports_a3.py`.
- [ ] Branch/store filter on P&L deferred (journals have no store_id yet).

## P1 acceptance criteria (preview)

- POS sale can record multiple tender lines (`pos_payments`) that sum to total; GL routing per method.

## C1 acceptance criteria (preview)

- Credit sale / invoice over limit requires override reason + audit event; role-gated.

## Sign-off

Stage 3 exit will be recorded in `docs/STAGE_3_EXIT_CRITERIA.md` with a freeze ADR when P0 workstreams are complete.
