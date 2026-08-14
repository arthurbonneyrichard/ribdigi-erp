# ADR-490: Tenant → Company Hierarchy (Workspace Context)

**Status:** Accepted  
**Date:** 2026-08-14  
**Related:** [ADR-001](ADR_001_TENANCY.md), [ADR-005](ADR_005_USER_STORE_ASSIGNMENT.md), [ADR-137](ADR_137_PLATFORM_PRINCIPAL.md), [ADR-002](ADR_002_BILLING_DEFERRED.md)

## Context

RIBDIGI MVP historically **collapsed Tenant ≈ Company**: `tenants.company_name` held the operating business, and tenant admins (`company_admin`) received full ERP module permissions. Product requirement is:

```text
Platform → Tenant (SaaS customer) → Company (operating business)
  → Branch / Store / Warehouse → Users → Roles / Permissions
```

Tenant Owner/Admin must **not** automatically access company operational data (POS, sales, stock, finance). Access requires explicit **company membership** and an active **company workspace**.

ADR-005 (user↔store membership) remains deferred. This ADR introduces **user↔company membership**, which is orthogonal.

## Decision

1. **Separate entities:** `Tenant` (SaaS account) and `Company` (operating business under a tenant). Shared-schema + `tenant_id` (ADR-001) remains; company-owned rows also carry `company_id`.
2. **Backfill:** Each existing tenant receives one default `Company` from `tenants.company_name` / industry / currency. Existing operational rows backfill to that company.
3. **Membership:** `user_company_memberships` links users to companies with a company role. Tenant-level roles (`tenant_owner`, `tenant_admin`, legacy `company_admin`/`super_admin`) may administer the tenant workspace without implying ops access.
4. **Workspace context:** Session claims include `workspace_kind` ∈ {`platform`,`tenant`,`company`} and optional `company_id`. Clients may send `X-Workspace-Kind` and `X-Company-ID`; the server verifies membership and never trusts client IDs alone.
5. **Authorization:** Operational modules (POS, sales, inventory, purchasing, expenses, accounting, credit, reports, stores, warehouse, …) require `workspace_kind=company` + membership + RBAC. Tenant modules (tenant dashboard, companies CRUD, subscription/limits, tenant settings) require `workspace_kind=tenant` (or platform for House APIs).
6. **Subscription limits:** Enforce `max_companies` (and related caps) on the tenant from plan metadata / tenant columns. Live billing remains deferred (ADR-002); limits are real gates, not fabricated MRR.
7. **Business types:** Configurable `business_types` catalog (not hard-coded application branches).
8. **Store membership:** Still deferred (ADR-005). Store context remains session/document + `stores.manager_id`.

## Consequences

- Existing single-company tenants keep working after backfill; cashiers default into company workspace.
- Tenant admins default into **tenant** workspace and must switch to a company to operate ERP modules.
- Multi-company tenants get real `company_id` isolation.
- Does **not** Complete ADR-002 billing, ADR-005 store membership, or schema-per-tenant.

## Phase 2 follow-up (2026-08-14)

- Operational **list** endpoints for sales docs, purchasing, expenses, COA, journals, customers/suppliers, stores, and warehouses apply `company_scope_filter`.
- Matching **creates** stamp `company_id` for invoices, expenses, parties, POs, stores/warehouses, and catalog rows.
- Unique keys for accounts, expense/product categories, brands, units, warehouses, products, and customer groups are company-scoped (`20260814_0097`).

## Phase 3 follow-up (2026-08-14)

- Sales quotations/orders/returns and purchasing PR/GRN/returns/invoices stamp `company_id` on create; GETs use `assert_record_company`.
- Stock movements, stock transfers, and stock counts are company-filtered on list/export; creates stamp `company_id`.
- Sales/purchase invoice CSV exports apply company scope.
- Remaining PARTIAL: some report aggregations and legacy export routes may still be tenant-only; journal create stamping and recurring-expense helpers can go further.

## Phase 4 follow-up (2026-08-14)

- Journal create / COA create / recurring expense create stamp `company_id`; recurring list/export/generate are company-scoped; journal GET uses `assert_record_company`; journal CSV export filters by company.
- Critical report aggregations (`sales_daily`, `inventory_valuation`, `purchases_summary`, `expenses_summary`, `/reports/summary`) accept `company_id` from workspace claims.
- Membership admin API: `GET/POST /companies/{id}/memberships`, `DELETE /companies/{id}/memberships/{user_id}`.
- Remaining PARTIAL: other report slices (monthly sales, product/customer breakdowns, credit aging, dashboard KPIs) and some legacy exports may still be tenant-wide; ADR-002 billing and ADR-005 store membership remain deferred.

## Phase 5 follow-up (2026-08-14)

- Remaining sales/inventory/purchasing report slices accept workspace `company_id` (monthly, by product/customer/salesperson/store, inventory balance/movements/low-stock/expiry, purchases by supplier/pending/returns).
- Credit AR/AP aging (+ aging CSV) company-scoped; customer/supplier/COA/expense-category CSV exports company-scoped.
- Company dashboard KPIs, revenue chart series, and expense-by-category slice use company filters (users/roles remain tenant-level).
- Remaining PARTIAL: accounting P&L / cash-flow / trial-balance and some payment-register exports may still be tenant-wide; ADR-002 billing and ADR-005 store membership remain deferred.

## Phase 6 follow-up (2026-08-14)

- Trial balance, P&L, cash flow, and balance sheet (APIs + CSV exports) accept workspace `company_id`; account balance rebuilds and liquid GL selection are company-filtered.
- Customer/supplier payment registers (list + CSV) filter by company; payment creates stamp `company_id`.
- Dashboard MTD P&L uses company scope.
- Remaining PARTIAL: some outstanding-bill / statement exports and liquid-account helpers may still be tenant-wide; ADR-002 billing and ADR-005 store membership remain deferred.

## Phase 7 follow-up (2026-08-14)

- Customer/supplier outstanding bills, statements, and supplier payment schedules (APIs + CSV) filter by workspace `company_id` and reject cross-company party access.
- Liquid account list/export/create/update are company-scoped; creates stamp `company_id` and use company-scoped uniqueness for account codes.
- Bank statement list/export/create/import stamp and filter `company_id`; statement GET rejects foreign-company rows.
- Remaining PARTIAL: bank-connection sync helpers and some adjacent finance tooling may still be tenant-wide; ADR-002 billing and ADR-005 store membership remain deferred.

## Phase 8 follow-up (2026-08-14)

- Bank connections (list/export/create/update/delete/sync) stamp and filter by workspace `company_id`; sync creates company-stamped bank statements.
- Cheques (list/export/get/deposit/clear/bounce/cancel) are company-scoped; creates from payments stamp `company_id`; lifecycle journals use company COA.
- Liquid transfers, COA account GET, account ledger/transactions (+ CSV), and opening-balance posts are company-scoped.
- Remaining PARTIAL: FX exchange-rate catalog may remain tenant-shared by design; ADR-002 billing and ADR-005 store membership remain deferred.

## Phase 9 follow-up (2026-08-14)

- POS sessions (open/current/list/close/report) stamp and filter by workspace `company_id`.
- POS sales (create/list/export/receipt) and payments stamp `company_id`; journals use company COA.
- Held carts (list/create/resume/discard/expire) are company-scoped; product lookup and products CSV export filter by company.
- Remaining PARTIAL: tax rates/tax reports, AI ops aggregations, report schedules/notifications; FX may stay tenant-shared; ADR-002 billing and ADR-005 store membership remain deferred.
