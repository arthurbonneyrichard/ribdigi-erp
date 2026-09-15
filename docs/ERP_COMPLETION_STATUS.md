# Ribdigi Business ERP — Completion Status

**Date:** 2026-09-15  
**Audience:** Product + engineering (Commercial MVP / SMB retail–wholesale)  
**Related:** root `PRODUCTION_READINESS.md`, `docs/DEVELOPMENT_ROADMAP.md`, `docs/BUSINESS_REQUIREMENTS_DOCUMENT.md`

> Roadmap checkboxes in `DEVELOPMENT_ROADMAP.md` lag the codebase. Prefer this document + live routes/APIs for “what ships.”

## Honest completeness

| Lens | Estimate |
|------|----------|
| **SMB retail / wholesale ERP** (multi-store inventory, POS, sales, purchasing, credit, basic GL, tax, expenses, reports, platform billing) | **~78–85%** of a shippable commercial MVP |
| **Full “enterprise ERP”** (MRP, advanced WMS putaway, payroll/HRIS, native Open Banking, marketplace connectors, mobile apps) | **~55–65%** — large domains remain out of scope or Partial |

## Module inventory

| Domain | Status | Evidence (UI / API) | Notes |
|--------|--------|---------------------|--------|
| Auth / users / RBAC / 2FA / sessions | **Done** | `/security`, `/users`, auth routes | Passkeys + TOTP; session revoke |
| Company / branding / SMTP / SMS | **Done** | `/company` | Logo, email/SMS settings |
| Multi-store / branches / warehouses / departments | **Done** | `/stores`, `StoreSwitcher`, `StoreProvider` | Header store context exists |
| Inventory catalog / stock / transfers / counts | **Done** (ops) / **Partial** (WMS) | `/inventory` | Strong SKU/stock UI; **no bin/putaway**; store context under-wired |
| POS | **Done** | `/pos` | Sessions, tenders, receipts; USB/serial drawer soft |
| Sales (QT / SO / SI / returns) | **Done** | `/sales` | Uses store context |
| Purchasing (PR / PO / GRN / PI / returns) | **Done** (flows) / **Partial** (store) | `/purchasing` | APIs support `warehouse_id`; UI ignored header store |
| Customers / suppliers / credit | **Done** | `/sales`, `/purchasing`, `/credit` | Aging, payments, FX packaging |
| Accounting / journals / bank recon / cheques | **Done** | `/accounting` | P&amp;L had local store filter; not synced to header |
| Expenses / recurring | **Done** | `/expenses` | Store-aware |
| Tax | **Done** | `/tax` | Store-aware reports |
| Reports / export / schedules | **Done** | `/reports` | Store-aware |
| Dashboard | **Partial** | `/dashboard` | KPIs tenant-wide; no active-store filter |
| Notifications | **Done** | `/notifications` + shell bell | |
| Audit | **Done** | `/audit` | |
| Backup | **Done** (logical) / **Partial** (DR) | `/backup` | Logical backup/restore; PITR/ops runbooks separate |
| Integrations (API keys / webhooks) | **Done** | `/integrations` | |
| AI assist | **Partial** | `/ai` | Rule/heuristic packaging; full LLM chat not “complete” |
| Platform / packages / tenant admin | **Done** | `/platform/*` | Subscription + modules + store entitlement |
| Jobs / Celery admin | **Done** | `/jobs` | |
| Manufacturing / MRP / BOM | **Missing** | — | Document only; not MVP |
| HR / payroll | **Missing** | — | Out of MVP |
| Multi-bin / putaway / location hierarchy | **Missing** | — | Roadmap Remaining; schema not present |
| Open Banking / Plaid | **Missing** | — | HTTP/mock bank feeds only |
| FIFO / LIFO costing | **Partial** | Inventory valuation | Standard/cost path; advanced costing soft |
| Mobile native apps | **Missing** | — | Responsive web only |
| Marketplace / e‑commerce connectors | **Missing** | — | |

## Top gaps blocking “complete ERP” (business impact)

1. **Header store context not applied on Inventory / Purchasing** — cashiers/managers switch Store in the shell, but stock and buy flows still default to first warehouse / no warehouse. Highest UX integrity fix for multi-store MVP. *(This session: address.)*
2. **Dashboard ignores active store** — HQ vs branch view unclear for managers.
3. **Accounting P&amp;L store filter desynced** from header switcher — confusing dual controls.
4. **Inventory multi-bin / putaway** — blocks warehouse-grade WMS claims (large; document, don’t fake).
5. **Costing methods (FIFO/LIFO)** — retail MVP often OK on standard cost; wholesale may need later.
6. **AI / chat completeness** — assist exists; do not market as full BR-21 LLM suite.
7. **Native bank Open Banking** — recon works with import/HTTP; not bank-grade connectivity.
8. **Manufacturing / HR** — out of retail–wholesale MVP; epic later if product expands.
9. **Cross-tenant isolation automated matrix** — security hardening Remaining (ops/QA).
10. **USB/serial cash drawer** beyond TCP/browser — POS hardware soft gap.

## Recommended epic order

1. **Store-context consistency** (inventory, purchasing, dashboard, accounting) ← current
2. Dashboard store-scoped KPIs
3. Inventory valuation / costing honesty (document method; FIFO only if required)
4. Isolation / DR test matrix (PRODUCTION_READINESS Remaining)
5. Hardware drawer + receipt polish
6. AI packaging honesty + optional LLM (flagged)
7. Defer: MRP, payroll, multi-bin WMS, Open Banking, marketplaces

## This session

- Authored this status document.
- Wired **Inventory** and **Purchasing** to `useStoreContext` (warehouse defaults / filters + PO/GRN `warehouse_id`).
- Synced **Accounting** P&amp;L store filter with header active store when unset.
- Clarified **StoreSwitcher** help text for inventory/purchasing.

## Do not regress

- Add Product price labels stay **Actual price** / **Selling price** (no “What you paid / sell at” helper copy).
