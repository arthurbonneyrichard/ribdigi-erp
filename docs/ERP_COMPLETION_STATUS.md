# ERP completion status (working tracker)

Living tracker for Commercial MVP ERP gaps. Update after each meaningful ship.
Last updated: 2026-09-15 (dashboard store-scoped KPIs + accounting trial balance).

## Overall

| Segment | Estimate | Notes |
|---|---|---|
| Core SMB retail/wholesale path (sell, buy, stock, cash, basic books) | **~88%** | Header store now scopes Dashboard KPIs + Inventory/Purchasing ops + Accounting P&L/TB |
| Full documented ERP (MRP, HR, Open Banking, multi-company-under-tenant) | **~72%** | Large BR slices still missing by design for MVP |

MVP target is the SMB path, not every BR-21 / WMS / HR line.

## Module snapshot

| Area | Status | Gaps / notes |
|---|---|---|
| Auth / tenancy / RBAC | Done (MVP) | Shared-schema `tenant_id`; package modules |
| Multi-store / warehouses | Done (MVP) | Entitlements; header store switcher |
| Catalog / products | Done (MVP) | Actual/Selling price labels kept |
| Inventory ops | Done (MVP) | Header store scopes stock-in/out/adjust/transfers/warehouse stock |
| Purchasing | Done (MVP) | Header store scopes PR/PO warehouse defaults + lists |
| Sales / POS | Done (MVP) | Store on documents; POS session store |
| Credit AR/AP | Done (MVP) | Payments, aging |
| Expenses | Done (MVP) | Categories, approval, recurring |
| Accounting | Done (MVP) | COA, journals; **P&L + trial balance honor header store** |
| Reports | Partial | Many filters; not every tab fully store-scoped |
| Dashboard | **Done (MVP)** | **KPIs honor header store** (`GET /dashboard?store_id=`) |
| Tax | Done (MVP) | Rates, filing GH |
| Backup / audit / jobs | Done (MVP) | |
| Integrations / webhooks | Done (MVP) | |
| AI | Partial | Insights/docs; not full BR-21 chat |
| WMS advanced (bins/putaway) | Missing | Beyond warehouse stock |
| MRP / HR / Open Banking | Missing | Out of SMB MVP |
| Multi-company-under-tenant | N/A | Company == Tenant |

## This session (2026-09-15) — Dashboard store-scoped KPIs

- **Backend:** `GET /dashboard` accepts optional `store_id`; `build_dashboard(..., store_id=)` scopes sales/purchases/expenses/stock/recent/trends/top products to that store (or its warehouses for stock). Party counts + subscription remain tenant-wide. Invalid store → 404.
- **Frontend Dashboard:** `useStoreContext` → refetch `/dashboard?store_id=` when header store changes; banner when scoped.
- **Accounting:** Trial balance query now includes header `store_id` (same as P&L); both reload when header store changes.

Prior session: Inventory/Purchasing/Accounting P&L header-store wiring (`6d1bb09e43`).

## Top remaining gaps (next sessions)

1. **Expense OCR / AI document draft** confidence and edge cases (if still partial in UI)
2. **Reports** — remaining tabs without store/warehouse filter parity
3. **Multi-bin / putaway WMS** (if product wants it for MVP+)
4. **FIFO/LIFO costing** honesty vs standard-only valuation
5. **Industry COA packs** / MRP / HR / Open Banking (documented missing)

## Definition of done (per gap)

- API + tenant/RBAC + validation
- UI wired (or honest “not in UI”)
- Focused test or tsc where practical
- This file updated
- No junk commits; Actual/Selling labels unchanged
