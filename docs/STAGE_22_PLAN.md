# Stage 22 Plan — Expenses, Ledger, Credit & Tax Surface Fidelity

**Status:** Open  
**Base:** Expenses fidelity → Accounting ledger → Credit & tax surface → Fidelity closeout  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Open ADR:** [ADR-049](ADR_049_STAGE22_OPEN.md)

Stage 22 closes commercial-MVP finance-surface fidelity after Stage 21 freeze. Expense, COA, cash/bank/recon/cheques, AR/AP, customer credit, and tax engines already exist (Stages 3 / 8 / 10 / 14 / 15). This track proves remaining unchecked BR-9–12 ACs with live evidence and docs sync — **not** paid billing, schema-per-tenant, i18n packs, Open Banking, tax e-file portals, K8s/WAL/PITR, Grafana, certified 1000-VU, or reopening Stages 1–21.

## Product outline (owner)

```
Expenses fidelity
 ├── Categories · budgets · entry fields (BR-9.1–9.2)
 ├── Approval matrix · comments · approver notify (BR-9.3)
 └── Recurring generate · notify · skip/modify (BR-9.5)

Accounting ledger fidelity
 ├── COA types · hierarchy · opening balances (BR-10.1)
 ├── Cash/bank · deposits/transfers · recon · cheques (BR-10.3)
 └── AR/AP aging · payments · overdue · report export (BR-10.4–10.6)

Credit & tax surface
 ├── Customer credit limits · override · statements (BR-11.1)
 └── Tax types · inclusive/exclusive · compound (BR-12.1)

Fidelity closeout
 ├── Docs / BR-9–12 / readiness / USER_MANUAL / API sync
 └── Exit + freeze
```

## Delivery rules

1. One workstream at a time (full AC + automated tests before the next).
2. Prefer extending proven expense / accounting / credit / tax engines — do not rewrite stacks or invent fake success.
3. No demo data / fake success. Alembic only when schema is required.
4. After each feature: tests → commit → push → PR update.
5. Do not reopen Stage 1–21 feature scopes. BR-9.4 attachments, BR-10.2 journals, BR-11.2 supplier credit, BR-12.2–12.3 calculation/reports remain Complete under prior stages (cite under D1 only where needed). Industry-agnostic COA honesty (not per-industry packs) remains MVP.

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **E1** | Expense categories & entry fidelity (BR-9.1–9.2) | P0 | COMPLETE |
| **A1** | Expense approval & recurring fidelity (BR-9.3, 9.5) | P0 | COMPLETE |
| **C1** | COA fidelity (BR-10.1) | P0 | COMPLETE |
| **B1** | Cash/bank, recon, cheques fidelity (BR-10.3) | P1 | COMPLETE |
| **P1** | AR/AP aging, payments, overdue + financial export (BR-10.4–10.6) | P1 | PENDING |
| **R1** | Customer credit surface fidelity (BR-11.1) | P1 | PENDING |
| **T1** | Tax configuration fidelity (BR-12.1) | P1 | PENDING |
| **D1** | Spec / BR-9–12 / readiness / USER_MANUAL / API fidelity sync | P2 | PENDING |
| **H22x** | Stage 22 exit criteria + freeze ADR | Exit | PENDING |

## Explicitly out of this pass

- Paid billing (ADR-002); schema-per-tenant (ADR-001); i18n packs (ADR-006)
- User↔store membership (ADR-005); hard-delete with archival (ADR-003)
- External LLM / Prophet / IsolationForest vendor model upgrades
- PO OCR auto-apply (expense/PI OCR remains Stage 10)
- Kubernetes / Helm production chart; GHA → staging K8s deploy
- Full Prometheus / Grafana / PagerDuty stack; centralized SIEM
- pg_dump / WAL / S3 offsite PITR; PgBouncer
- Certified ~1000-VU capacity certificate; vendor penetration test / ZAP-in-CI Top 10
- Multi-bin; FIFO/LIFO/WA; PO Kanban polish
- WebSocket realtime notifications; Open Banking; tax e-file portals
- Richer WYSIWYG template designer
- Reopening Stages 1–21 frozen feature scopes (including Stage 14 finance chain holes already closed)

## E1 acceptance criteria

- [x] Predefined + custom expense categories and category budget allocation proven.
- [x] Expense entry fields (date/category/amount/method/reference/payee/description) proven.
- [x] Automated proof: `backend/tests/test_expense_categories_entry_e1.py`.
- [x] BR-9.1–9.2 synced with evidence (store/dept already Stage 14 — cite, do not re-scope).

## A1 acceptance criteria

- [x] Configurable thresholds / multi-level approval / comments / approver notify proven.
- [x] Recurring frequency, auto-generate, notify-before, skip/modify proven.
- [x] Automated proof: `backend/tests/test_expense_approval_recurring_a1.py`.
- [x] BR-9.3 / 9.5 synced with evidence.

## C1 acceptance criteria

- [x] Seeded COA, account types, hierarchy, non-system CRUD, opening balances proven.
- [x] Automated proof: `backend/tests/test_coa_fidelity_c1.py`.
- [x] BR-10.1 synced with evidence (industry-agnostic system COA honesty).

## B1 acceptance criteria

- [x] Cash/bank accounts, deposits/withdrawals/transfers, bank reconciliation, cheque lifecycle proven.
- [x] Automated proof: `backend/tests/test_cash_bank_recon_b1.py`.
- [x] BR-10.3 synced with evidence (Open Banking adapters remain deferred).

## P1 acceptance criteria

- [ ] AR/AP auto from invoices, aging, payments/partial, overdue/due notifications, financial PDF/Excel export proven.
- [ ] Automated proof: `backend/tests/test_ar_ap_export_p1.py`.
- [ ] BR-10.4–10.6 synced with evidence (P&L/TB/cash-flow already Stage 3/14/15 — export focus for 10.6).

## R1 acceptance criteria

- [ ] Credit limit, block+override, outstanding balance, payment collections, customer statement proven.
- [ ] Automated proof: `backend/tests/test_customer_credit_r1.py`.
- [ ] BR-11.1 synced with evidence (allocate already Stage 14 R1 — cite).

## T1 acceptance criteria

- [ ] Tax types, inclusive/exclusive pricing mode, compound tax proven.
- [ ] Automated proof: `backend/tests/test_tax_config_fidelity_t1.py`.
- [ ] BR-12.1 remaining ACs synced (rates/category/calc/reports already Stage 10/14/15/21 — cite).

## D1 acceptance criteria

- [ ] BR-9–12, finance readiness, USER_MANUAL / API aligned — `docs/STAGE_22_FIDELITY.md`.
- [ ] Guard test: `backend/tests/test_stage22_fidelity_d1.py`.

## H22x acceptance criteria

See workstream table; filled when exit workstream starts.

## Sign-off

E1–B1 complete. Pending P1 → H22x. Stages 1–21 remain frozen for their scopes.
