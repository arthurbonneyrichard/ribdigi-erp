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

## Phase 10 follow-up (2026-08-14)

- Tax rates (list/create/export/get/update/set-default/calculate) stamp and filter by workspace `company_id`; defaults clear only within the active company.
- Tax report, tax report CSV, filing pack, and government filing packs filter sales invoices / POS / purchase invoices / POs by `company_id`.
- Category tax-rate validation and product default-tax resolution prefer the product/category company.
- Remaining PARTIAL: AI ops aggregations, report schedules/notifications; FX may stay tenant-shared; ADR-002 billing and ADR-005 store membership remain deferred.

## Phase 11 follow-up (2026-08-14)

- AI insights, sales/expenses/purchases analysis, inventory low-stock/forecast/dead-stock (+ CSV exports) filter by workspace `company_id`.
- Cross-domain AI analysis threads company scope into domain analyzers; insight publish / stockout notify stamp `Notification.company_id`.
- Report schedules (list/create/export/get/update/delete/run) stamp and filter by company; scheduled exports pass `company_id` into report builders.
- Notifications list/unread/export filter by company; creates accept `company_id`.
- Remaining PARTIAL: AI chat history/templates/customers/documents/security may still be tenant-wide; FX may stay tenant-shared; ADR-002 billing and ADR-005 store membership remain deferred.

## Phase 12 follow-up (2026-08-14)

- AI chat helpers/history stamp and filter by workspace `company_id`; draft PO create stamps company.
- AI report templates CRUD/export and NL report generate/export pass `company_id` into report builders.
- Customer intelligence/assist and document OCR matching filter parties/products/categories by company.
- Security alert scan prefers company-scoped audit rows (null-company auth events remain visible); notify stamps company.
- Remaining PARTIAL: FX may stay tenant-shared by design; ADR-002 billing and ADR-005 store membership remain deferred.

## Phase 13 follow-up (2026-08-14)

- Dashboard summary / sales-trend / top-products / expenses / stock-alerts (+ exports) filter by workspace `company_id`.
- Catalog categories/brands/units list/export/mutate and cache keys are company-scoped; creates stamp `company_id`.
- Expense categories and customer groups list/create/export stamp and filter by company.
- Inventory low-stock and expiring-batch alerts (+ exports) and product variants export are company-scoped.
- Stores/warehouses CSV exports filter by company; store/warehouse GET/PATCH reject cross-company IDs.
- **FX exchange-rate catalog remains tenant-shared by design** for MVP (shared base currency / rates); company-specific FX catalogs deferred.
- Remaining PARTIAL: audit-log list stamping, branches/departments org units, backup gating to tenant workspace; ADR-002 billing and ADR-005 store membership remain deferred.

## Phase 14 follow-up (2026-08-14)

- Audit log `record_event` stamps optional `company_id`; HTTP mutation middleware stamps verified `request.state.company_id`; list/export filter by company (null-company auth/system events remain visible). Chain verify / cold archive stay tenant-wide.
- Branches and departments list/export/create/update stamp and filter by workspace `company_id`; creates require company workspace; serialize/export include `company_id`.
- Backup APIs require **tenant workspace** (removed from company-operational modules); company workspace cannot create/list/restore full-tenant dumps. Frontend backup nav moved to tenant workspace and page switches context on load.
- Remaining PARTIAL: branch/department unique keys remain `(tenant_id, code)` (not company-scoped); ADR-002 billing and ADR-005 store membership remain deferred; FX stays tenant-shared.

## Phase 15 follow-up (2026-08-14)

- Company-scoped uniqueness (Alembic `20260814_0098` + models): branches, departments, stores, product variants (SKU), parties (`kind`+`code`).
- App-level uniqueness checks filter by `company_id`; variant create stamps `company_id` from parent product.
- Product GET/PATCH and variant create/patch reject cross-company IDs; product SKU clash checks are company-scoped; catalog meta FK resolve respects company.
- Store create uniqueness + branch assignment verify company; notification mark-read / mark-unread / mark-all-read filter by company (null-company notes remain visible).
- Remaining PARTIAL: document number series still tenant-wide; ADR-002 billing and ADR-005 store membership remain deferred; FX stays tenant-shared; API keys/webhooks/offline devices remain tenant-integration by design.

## Phase 16 follow-up (2026-08-14)

- Document numbering series move to `Company.document_numbering` (Alembic `20260814_0099`); allocate locks the company row; DOC_KEY uniques are `(tenant_id, company_id, …)`.
- `GET/PATCH /tenants/me` (and document-settings export) use active company series when in company workspace; tenant JSON remains legacy fallback/seed.
- Quote→order and order→invoice (and PR→PO) convert paths stamp/allocate with the parent document’s `company_id` so series stay on the company counter.
- Nested product surfaces (images, batches, warehouse-stock) reject cross-company product IDs; product images stamp `company_id`.
- Stock count and stock transfer by-id + lifecycle paths filter by workspace `company_id`.
- Remaining PARTIAL: print templates still tenant-level; ADR-002 billing and ADR-005 store membership remain deferred; FX stays tenant-shared; API keys/webhooks/offline devices remain tenant-integration by design.

## Phase 17 follow-up (2026-08-14)

- Print templates (`invoice_print_template`, `receipt_print_template`, `document_header`/`document_footer`) move to `Company` (Alembic `20260814_0100`); `GET/PATCH /tenants/me`, preview, export, and print/receipt builders prefer the active company series; tenant columns remain legacy seed/fallback.
- Print routes (invoice/quotation/credit note/PO/debit note) assert company record ownership and brand from the company (or claims) context.
- Global search, party history (+ export), and legacy `/sales`/`/purchases` transaction list/create stamp and filter by workspace `company_id`.
- Remaining PARTIAL: ADR-002 billing and ADR-005 store membership remain deferred; FX stays tenant-shared; API keys/webhooks/offline devices remain tenant-integration by design.

## Phase 18 follow-up (2026-08-14)

- Lifecycle mutate endpoints (send/post/cancel/convert/confirm/ship/… for sales, purchasing, expenses) call `assert_record_company` so cross-company IDOR cannot mutate sibling docs.
- Sales/purchasing pipeline CSV exports and expense CSV export apply `company_scope_filter`.
- Ops number uniques (customer/supplier payments, POS sessions, journal entries, stock transfers/counts, purchase requests) are `(tenant_id, company_id, …)` via Alembic `20260814_0101`; session/transfer counters count within company.
- Product/stock CSV import stamps and filters by workspace `company_id`.
- Frontend `authHeaders()` sends workspace headers on raw download/fetch paths across sales, purchasing, inventory, expenses, accounting, credit, POS, stores, reports, tax, and company settings.
- Remaining PARTIAL: ADR-002 billing and ADR-005 store membership remain deferred; FX stays tenant-shared; API keys/webhooks/offline devices remain tenant-integration by design; barcode uniqueness and some child-row stamps remain secondary.

## Phase 19 — Dynamic workspace branding (2026-08-14)

- Sidebar branding is driven by workspace context (platform / tenant / company), not static copy.
- Company serialize + `/me` / `/workspace` expose `has_logo`, `business_type_label`, and tenant branding fields; `GET/POST/DELETE /companies/{id}/logo` and `PATCH /companies/{id}` (name/profile) use existing media storage (`logos` category) with MIME/size validation.
- Branding mutations require `companies` write **and** an admin-like role (`assert_can_manage_company_branding`); cashiers cannot change logos/names. Cross-tenant and cross-company IDOR covered by tests.
- Frontend `WorkspaceBrand` shows logo or initials, business type + branch/store subtitle when expanded; tenant/platform contexts do not keep stale company logos. Create-company and company settings support optional logo upload/replace/remove.
- Print/receipt branding already prefers company logo via `print_branding.tenant_document_brand` when a company logo exists.
- Remaining PARTIAL: SVG logos remain unsupported by storage allow-list (security); desktop sidebar collapse chrome is optional (component supports `collapsed`); ADR-002/005 and FX tenant-shared remain deferred.

## Phase 20 — Barcode uniques + child-row stamps (2026-08-14)

- Product/variant barcode clash checks and allocation are company-scoped (`barcodes.py`); create/patch/generate APIs pass `company_id`; generate + label resolve assert company ownership (IDOR-safe).
- Alembic `20260814_0102` adds partial unique indexes `(tenant_id, company_id, barcode) WHERE barcode IS NOT NULL` on `products` and `product_variants`; models mirror company-scoped barcode uniqueness.
- Child creates stamp `company_id` from parent/product: `ProductBatch`, `WarehouseStock`, `StockReservation`, purchasing line items (PR/PO/GRN/return/invoice), PO amendments, stock transfer items, party contacts, expense/PR approval actions.
- Remaining PARTIAL: cheque / offline `client_request_id` uniques may still be tenant-wide; bank clearing group rows; ADR-002 billing and ADR-005 store membership remain deferred; FX stays tenant-shared; API keys/webhooks/offline devices remain tenant-integration by design.

## Phase 21 — Cheque / POS idempotency uniques + clearing stamps (2026-08-14)

- Cheque uniqueness is `(tenant_id, company_id, cheque_number, direction)` (Alembic `20260814_0103`); `assert_cheque_number_available` returns 409 within a company while allowing the same number in sibling companies.
- POS `Transaction.client_request_id` uniqueness is company-scoped (partial unique where key is set); `find_sale_by_client_request_id` / `record_pos_sale` replay only within the active company.
- `BankClearingGroup` and `BankClearingBookLink` stamp `company_id` from the parent bank statement on multi-line clear-group create.
- Remaining PARTIAL: ADR-002 billing and ADR-005 store membership remain deferred; FX stays tenant-shared; API keys/webhooks/offline devices remain tenant-integration by design.

## Phase 22 — Expense/bank IDOR, transfer stamps, serialize parity (2026-08-14)

- Expense approve/reject/delete/OCR/attachment routes call `assert_record_company` so sibling-company expenses cannot be mutated or downloaded.
- Bank statement clear-group / auto-clear / complete / dissolve gate on company-scoped statement (and dissolve asserts statement/group ownership).
- PO amendments list and credit early-discount quotes assert record company ownership.
- Stock transfer ship/receive/cancel stamp `StockMovement.company_id`; lazy default warehouse and transfer-ship notifications stamp `company_id`.
- Serialize helpers expose `company_id` for cheques, expenses, bank statements/lines/groups, warehouses/transfers, COA/journals, sales invoices, and POS sale results.
- Remaining PARTIAL: broader notification scan company filters; remaining serialize peers (PR/PO/GRN/holds/products); ADR-002/005 and FX/API-keys deferred by design.

## Phase 23 — Notification stamps, serialize peers, mutate IDOR (2026-08-14)

- Notification scans (low stock, payment due, quotation expiry, recurring expense) and domain emits (expense approval, purchasing, sales invoice/docs, POS shift variance) stamp `company_id` from the source entity.
- Serialize helpers expose `company_id` for PR/PO/GRN/purchase return/invoice/amendment, POS holds, products, quotations/orders/returns, customers/suppliers, and stock counts.
- Mutate IDOR: PR approve/reject; PI OCR/attachment; customer/supplier patch/delete/contacts/credit-limit; journal unpost/attachment; COA patch (company-scoped uniqueness); inventory adjust; variant delete; store reorder-policy assert product/store company.
- Remaining PARTIAL: ADR-002 billing and ADR-005 store membership remain deferred; FX stays tenant-shared; API keys/webhooks/offline devices remain tenant-integration by design; optional P2 serialize of payment registers/connectors and child-row contact serializers.

## Phase 24 — Payment IDOR, nested exports, budgets, P2 serialize (2026-08-14)

- Customer/supplier payment services and API routes assert party (and invoice/PO) company ownership; open-invoice allocation queries filter by `company_id`.
- Nested product variants list/export and batches/warehouse-stock export assert product company before read.
- Store inventory/sales (and CSV exports) pass `company_id` into `get_store`; party history/export assert company ownership before returning empty-or-scoped payloads.
- Expense category budgets list/export pass workspace `company_id` into `category_budget_variance`.
- Gallery image upload asserts product company before `save_upload`.
- Serialize helpers expose `company_id` for customer/supplier payments, contacts, stock movements, batches, product images, POS sales export rows, and bank connections.
- Remaining PARTIAL: ADR-002 billing and ADR-005 store membership remain deferred; FX stays tenant-shared; API keys/webhooks/offline devices remain tenant-integration by design; optional child-row serializers (approval actions, stock-count items, POS payment lines).

## Phase 25 — Create-path FK company asserts (2026-08-14)

- Added `workspace.assert_fk_company` for create-path related-row checks; `get_customer` / `get_supplier` accept optional `company_id`.
- Sales invoice/quotation/order and purchasing PR/PO create paths reject sibling-company customer/supplier/product/store/warehouse FKs.
- Inventory stock-in/out/opening and low-stock reorder-PO assert product (and supplier/warehouse) company; stock transfer and stock-count creates gate stores/warehouses/products by company.
- Expense create/update/recurring resolve category and store/department with company scope; `/reports/transfers` filters by workspace `company_id`.
- Child-row serialize exposes `company_id` for expense/PR approval actions, stock-count items, and POS payment lines.
- Remaining PARTIAL: ADR-002/005, FX tenant-shared, API keys/webhooks/offline devices deferred by design; deeper line helpers (GRN/return) and document-line serializers remain secondary.

## Phase 26 — Deeper create FK + document-line serialize (2026-08-14)

- GRN / purchase return / purchase invoice create paths `assert_fk_company` on PO/GRN; PI line prep and PO amend assert product company; supplier lookup and supplier-payment auto-allocate filter by workspace `company_id`.
- Sales return create asserts invoice company (API + `sales_docs.create_return`); POS sale asserts product company after line resolve.
- Document-line serialize exposes `company_id` on sales invoice/quotation/order/return items, PR/PO/GRN/return/PI items, journal lines, and stock-transfer items.
- Product warehouse-stock GET (and CSV export) scopes stock rows by company; recurring expense PATCH asserts company before mutate.
- Remaining PARTIAL: ADR-002/005, FX tenant-shared, API keys/webhooks/offline devices deferred by design.
