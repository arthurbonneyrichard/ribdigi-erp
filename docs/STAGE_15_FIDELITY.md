# Stage 15 Fidelity Notes — Sales Inventory–Ledger Chain

**Status:** Closed with Stage 15 D1  
**Chain:** Sales → Inventory → Customer balance → Tax → Accounting → Audit

## Corrections applied

| Area | Before | After |
|------|--------|-------|
| Invoice → ledger proof | Stage 12 C1 qty/total/JE total only | Stock movements, AR, tax report, JE codes `1100`/`4000`/`2100` (C1) |
| COGS / Inventory GL | Sale/POS journals AR/Revenue/Tax only | Dr COGS `5000` / Cr Inventory `1200` at qty × standard `cost_price`; return reverse (I1) |
| Invoice post atomicity | Line-by-line stock-out could partial-commit | Aggregated `INSUFFICIENT_STOCK` preflight before stock/AR/JE (H1) |
| Sales return chain | Restock without store warehouse; AR/JE not FX-safe; no JE `store_id` | Warehouse restock; `to_base` AR/JE; tax/COGS reverse; store on JE (R1) |
| Tax → filing proof | Filing tests often planted DB rows | Live HTTP-posted invoices (standard, RC memo, supply splits) feed `/reports/tax` + filing (T1) |
| Sales domain audit | Thin `invoice_posted`; no return audit | Enriched `invoice_posted` (stock/tax/AR); `sales_return_posted` (A1) |

## Evidence tests

- `backend/tests/test_sales_inventory_ledger_chain_c1.py`
- `backend/tests/test_sales_cogs_inventory_i1.py`
- `backend/tests/test_sales_invoice_atomicity_h1.py`
- `backend/tests/test_sales_return_chain_r1.py`
- `backend/tests/test_sales_tax_filing_t1.py`
- `backend/tests/test_sales_audit_a1.py`
- `backend/tests/test_stage15_fidelity_d1.py`

## Spec sync targets

- `docs/BUSINESS_REQUIREMENTS_DOCUMENT.md` — BR-5.2/7.4/7.5, BR-10.4/10.6 COGS, BR-12.2/12.3 live filing, BR-17.1 sales audits
- `docs/API_DOCUMENTATION.md` — §§7 invoices/returns, accounting auto-post COGS
- `docs/SECURITY_GUIDE.md` — `invoice_posted` / `sales_return_posted`
- `PRODUCTION_READINESS.md` — Sales / Accounting / Tax / Audit bullets
- `docs/USER_MANUAL.md` — Sales invoice/return + COGS notes
- `docs/DEVELOPMENT_ROADMAP.md` — Stage 15 D1 note
- `docs/LAUNCH_CHECKLIST.md` — C1–A1 / T1 / R1 evidence tests

## Deferred (not Stage 15)

Native Open Banking; tax e-file portals; FIFO/LIFO/WA; multi-bin; K8s/WAL/S3 PITR; Credit-engine rewrite; reopening Stage 12–14 scopes.
