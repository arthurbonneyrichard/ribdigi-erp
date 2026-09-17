# ERP Completion Status — Market readiness

**Last updated:** 2026-09-17  
**Overall estimate (SMB retail / wholesale core):** ~**94%**  
**Verdict:** **Live-complete for market** for core sell / buy / stock / cash / tax / multi-store operations.  
Larger domains (HR, MRP, Open Banking, native mobile) remain intentional post-market roadmap items — not stubbed.

## Market-ready checklist

| Area | Status | Notes |
|------|--------|-------|
| Auth / RBAC / 2FA / idle logout | Done | Shell **auth gate**: unsigned users cannot open `/pos`, `/inventory`, etc.; redirected to login |
| Copy deterrence on app shell | Done | Selection/copy/context-menu blocked outside form fields |
| Dashboard store KPIs | Done | Header store → `GET /dashboard?store_id=` |
| Inventory / Purchasing store+warehouse | Done | Header store scopes warehouses |
| POS / Sales / Credit / Tax | Done | Existing production flows |
| Expenses store filter | Done | List API + UI `store_id` |
| Accounting P&L / TB / BS / CF | Done | Header store wired |
| Cash / bank / reconcile | Partial | Tenant-wide by design (no store on liquid accounts) |
| Reports + branch/store sync | Done | Header store; branch aligns to store’s `branch_id` |
| AI draft expense store | Done | Defaults/syncs from header store (analysis APIs are tenant-wide) |
| Brand / login | Done | Logo sizing; Ribdigi House product → ribdigihouse.com |
| OpenAPI honesty tip stream | Exhausted | Through #1894 — do not invent thin tips |

## Module coverage

| Module | Status |
|--------|--------|
| Auth / Users / Security | Done |
| Company / Multi-store | Done |
| Inventory | Done (WMS multi-bin Partial) |
| POS / Sales | Done |
| Purchasing | Done |
| Expenses | Done |
| Accounting | Done (cash/bank store scope OOS) |
| Credit / Tax | Done |
| Reports | Done |
| Notifications / Audit / Jobs / Backup | Done |
| Integrations / Platform | Done |
| AI Assistant | Done (MVP; analysis not store-scoped in API) |
| HR / Payroll | Missing (roadmap) |
| Manufacturing / MRP / BOM | Missing (roadmap) |
| Open Banking / Marketplace / Native apps | Missing (roadmap) |

## Intentionally out of scope for v1 market launch

1. Store-attributed liquid GL / bank accounts (schema change required — do not fake filters)
2. Full MRP / BOM / shop floor
3. HR / payroll
4. Open Banking connectors
5. Native mobile clients
6. Third-party marketplace connectors

## Recent ship notes (this line)

- Auth gate + secure shell copy deterrence
- AI draft expense store defaults from header context
- Reports: branch filter syncs from selected/header store; department clears on branch mismatch
- Prior: dashboard/accounting/reports/inventory/purchasing/expenses store parity

## Go-live recommendation

1. Merge this branch (store parity + market hardening) with PR #300 brand/tip line as needed.
2. Deploy backend + frontend with production secrets, HTTPS, and email/2FA configured.
3. Seed first tenant admin account; do **not** expose anonymous ERP routes.
4. Post-launch: cash store schema (if multi-store cash drawers need GL split), then HR/MRP epics.
