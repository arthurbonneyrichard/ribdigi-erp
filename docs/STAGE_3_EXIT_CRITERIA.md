# Stage 3 Exit Criteria

**Status:** Met for Sales, POS & Financials hardening workstreams A1–A3, P1, C1 (2026-08-09)  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Freeze:** [ADR-012](ADR_012_STAGE3_FREEZE.md)  
**Plan:** [STAGE_3_PLAN.md](STAGE_3_PLAN.md)

Stage 3 exit closes the Sales, POS & Financials **hardening** track on top of engines that already existed for roadmap Phase 3. It is **not** a claim that every later-module BR is Complete.

## Workstream checklist

| ID | Workstream | Verdict | Evidence |
|----|------------|---------|----------|
| A1 | Journal unpost + open fiscal-period gate | COMPLETE | `POST /accounting/journal-entries/{id}/unpost`; open FY gate; recon block; Ledger UI; `test_journal_unpost_a1.py` |
| A2 | COA CRUD / hierarchy / opening balances | COMPLETE | `POST/PATCH /accounting/accounts`; `parent_id` tree; opening balance vs 3900; Alembic `0075`; `test_coa_crud_a2.py` |
| A3 | P&L date range + cash-flow O/I/F | COMPLETE | Dated P&L buckets; cash-flow operating/investing/financing; Reports UI; `test_financial_reports_a3.py` |
| P1 | POS split tender (`pos_payments`) | COMPLETE | Alembic `0076`; `payments[]` on `/pos/sales`; multi-debit GL; UI; `test_pos_split_tender_p1.py` |
| C1 | Credit-limit override + audit | COMPLETE | `credit:approve` + reason; audit `credit_limit_override`; Alembic `0077`; `test_credit_limit_override_c1.py` |
| H3 | Exit criteria + freeze ADR | COMPLETE | This document + ADR-012 |

## Explicitly deferred (not Stage 3 blockers)

- Branch/store filter on P&L (journals have no `store_id` yet)
- Native Open Banking / Plaid adapters
- Tax authority e-file portal submission
- Vendor-specific USB/serial POS drivers beyond TCP ESC/POS / browser bridge
- Items already deferred under Stage 1/2 ADRs (billing, i18n packs, schema-per-tenant, multi-bin, etc.)

## Sign-off rule

Stage 3 foundation exit is **met** when the table above has no CRITICAL/MISSING rows for A1–A3, P1, C1 and ADR-012 is accepted. Broader commercial MVP readiness remains in `PRODUCTION_READINESS.md`.
