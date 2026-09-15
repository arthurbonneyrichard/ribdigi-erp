# ERP Completion Status

**Product:** RIBDIGI BUSINESS ERP — Commercial MVP v1.0  
**Last updated:** 2026-09-15 (Accounting BS/CF + Reports header-store; prior: Dashboard store KPIs)  
**Overall estimate:** ~**89%** of Commercial MVP scope (docs + implemented surfaces). Remaining ~11% is mostly out-of-scope modules (HR / Manufacturing / Projects) and thin polish gaps.

Treat `/docs` BRD / architecture / API as authoritative. This file is a living roll-up, not a substitute for those specs.

## How to read this

| Status | Meaning |
|--------|---------|
| **DONE** | MVP acceptance criteria work end-to-end with automated coverage where expected |
| **PARTIAL** | Usable core path; gaps called out |
| **MISSING** | Not in Commercial MVP build (or explicitly deferred) |

Percentages are engineering judgment against BR module scope, not billable completeness.

## Module roll-up

| Area | BR | Status | Est. | Notes |
|------|----|--------|------|-------|
| Tenancy / packages / store limits | BR-1, BR-13 | DONE | 95% | Shared-schema + `tenant_id`; packages; `max_stores` / override / allocation |
| Multi-store / WH / branch / dept | BR-2, BR-13 | DONE | 92% | Entitlements; transfers; FEFO; drawer settings |
| Users / RBAC / custom roles | BR-3 | DONE | 93% | Record scope; soft-deactivate roles; CSV import honesty |
| Dashboard / notifications | BR-4, BR-15 | DONE | **92%** | Header **store** scopes `GET /dashboard?store_id=` KPIs; alerts center + prefs |
| Inventory / catalog | BR-5 | DONE | 94% | Products, variants, batches, counts, movements, CSV |
| Purchasing | BR-6 | DONE | 93% | PR→PO→GRN→PI→returns; OCR draft path |
| Sales | BR-7 | DONE | 93% | QT→SO→SI→returns; credit override |
| POS | BR-8 | DONE | 92% | Sessions, tenders, drawer, receipts |
| Expenses | BR-9 | DONE | 92% | Categories, approval matrix, recurring |
| Accounting | BR-10 | DONE | **93%** | COA, journals, period; **P&L + trial balance + balance sheet + cash flow** honor header store (`store_id`); cash/bank/reconcile stay tenant-wide (no API `store_id`) |
| Credit / FX | BR-11, BR-2.6 | DONE | 92% | AR/AP aging, payments, exchange rates |
| Tax | BR-12 | DONE | 90% | Rates, filing pack (GH), reports |
| Reports / export / schedules | BR-14 | DONE | **91%** | Store/branch/dept filters; empty page store falls back to header `useStoreContext`; warehouse stays page-local |
| Backup / DR | BR-16 | DONE | 88% | Logical backup + verify/restore; failure alerts |
| Audit | BR-17 | DONE | 90% | Chain verify; cold archive |
| Integrations | BR-18 | DONE | 90% | API keys, webhooks + deliveries, domain lookup |
| Auth / 2FA / passkeys | BR-19 | DONE | 92% | Login 2FA gate; WebAuthn; sessions |
| Company / print / email / SMS | BR-20, BR-15 | DONE | 91% | Profile, branding, SMTP/Twilio settings |
| AI assistants | BR-21 | PARTIAL | 70% | Insights, security scan, inventory/sales/expense/docs; chat fail-closed until provider |
| HR / Manufacturing / Projects | — | MISSING | 0% | Out of Commercial MVP |

## This session (2026-09-15) — Accounting BS/CF + Reports header-store

Continues after Dashboard store-scoped KPIs (`d550401088` on `cursor/dashboard-store-scoped-kpis-392e`).

1. **Accounting balance sheet** — `balanceSheetQuery()` → `GET /accounting/balance-sheet?store_id=` from header `useStoreContext` (same pattern as P&L / trial balance). Load BS / compare / Apply as-of honor scope.
2. **Accounting cash flow** — `cashFlowQuery()` → `GET /reports/cash-flow?store_id=` (no `/accounting/cash-flow` route). Apply cash flow uses the same header store.
3. **Reports shared filters** — when the page Store select is empty (“All stores”), `qs()` / `balanceSheetQs()` / `trialBalanceQs()` / export fall back to header `ctxStoreId` so shell store selection scopes tabs that already accept API `store_id`. Warehouse remains page-local (header has no warehouse).
4. **Not wired:** Accounting Cash & Bank / Reconcile — list/create APIs have no `store_id`; leave tenant-wide (honest gap).

### Prior on this branch (`d550401088`)

- Dashboard KPIs: `useStoreContext` → `GET /dashboard?store_id=`.
- Accounting trial balance: header store via `trialQuery()` (P&L already had header-or-local).

## Known gaps (next agents)

- Accounting **cash / bank / reconcile** ignore header store (no API `store_id` on those routes).
- Reports **warehouse** filter is page-local only (header has no warehouse).
- HR / Manufacturing / Projects remain out of MVP.
- AI chat remains PARTIAL until provider packaging is production-ready.

## Related docs

- `docs/BUSINESS_REQUIREMENTS_DOCUMENT.md`
- `docs/ARCHITECTURE_DOCUMENTS.md`
- `docs/API_DOCUMENTATION.md`
- `PRODUCTION_READINESS.md`
- `docs/ADR_001_TENANCY.md`
