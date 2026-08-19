# Stage 14 Fidelity Notes — Finance Closeout Chain

**Status:** Closed with Stage 14 D1; exit met (H14x / ADR-034)  
**Chain:** Expenses → Accounting (COA, JE, GL, TB, P&L, Cash Flow) → Credit → Tax

## Corrections applied

| Area | Before | After |
|------|--------|-------|
| Expense category → GL | Hardcoded debit `6000` on approve | `expense_categories.account_id` → expense COA; fallback `6000` (E1) |
| Expense org dims | Store optional; no department; recurring lacked dims | `expenses` / `recurring_expenses` `store_id` + `department_id` (E2) |
| Journal store dimension | None; P&L/cash-flow all-tenant only | `journal_entries.store_id`; store filter on JE list, P&L, cash-flow (A1) |
| Point-in-time statements | TB/BS used live balances; BS `as_of` was “now” only | `as_of_date` rebuilds from posted journals through that date (A2) |
| Tax rate lifecycle | Create/list/default only | `PATCH /tax/rates/{id}` edit/deactivate; `active_only`; period helpers monthly/quarterly/annually (T1) |
| Credit allocate UI | Always auto oldest-first from Credit page | Select invoice/bill/PO or Auto; payload sends document ids (R1) |
| Expense domain audit | Workflow `expense_approval_actions` only | `expense_submitted` / `expense_auto_approved` / `expense_level_approved` / `expense_approved` / `expense_rejected` (A3) |

## Evidence tests

- `backend/tests/test_expense_coa_chain_e1.py`
- `backend/tests/test_expense_org_dimensions_e2.py`
- `backend/tests/test_journal_store_dimension_a1.py`
- `backend/tests/test_trial_balance_as_of_a2.py`
- `backend/tests/test_tax_rate_lifecycle_t1.py`
- `backend/tests/test_credit_payment_allocate_r1.py`
- `backend/tests/test_expense_audit_a3.py`
- `backend/tests/test_stage14_fidelity_d1.py`
- `backend/tests/test_stage14_exit_h14x.py`

## Spec sync targets

- `docs/BUSINESS_REQUIREMENTS_DOCUMENT.md` — BR-9.2 (store/dept + COA), BR-10.6 (store + as_of), BR-11.1 allocate, BR-12.1/12.3 T1
- `docs/API_DOCUMENTATION.md` — §§9–12
- `docs/DATABASE_DOCUMENTATION.md` — expense/journal Stage 14 columns
- `docs/SECURITY_GUIDE.md` — expense audit actions
- `PRODUCTION_READINESS.md` — Expenses / Accounting / Credit / Tax bullets
- `docs/USER_MANUAL.md` — §§7–10
- `docs/DEVELOPMENT_ROADMAP.md` — Stage 14 D1 note
- `docs/LAUNCH_CHECKLIST.md` — E1–A3 / T1 / R1 evidence tests

## Deferred (not Stage 14)

Native Open Banking; tax authority e-file portals; K8s/WAL/S3 PITR; FIFO/LIFO/WA; rewriting Credit core beyond allocate UI; schema-per-tenant; paid billing.
