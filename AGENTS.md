# AGENTS.md — RIBDIGI BUSINESS ERP agent guidance

## Product hierarchy (permanent)

```text
RIBDIGI HOUSE (Platform Owner)
      ↓
Subscription Plan / Tenant.max_* entitlements
      ↓
Tenant (SaaS customer account)
      ↓
Company (operating business)
      ↓
Store / Branch / Warehouse
      ↓
Users + RBAC
```

## Subscription-Based Multi-Store Architecture

RIBDIGI HOUSE controls the maximum subscription entitlement for a Tenant
(`Tenant.max_stores`, optional `Tenant.max_stores_override`, synced from
`PLAN_CATALOG.soft_limits.stores` when a plan changes and no override is set).

Tenant Admin controls how available Store capacity is allocated to Companies
(`Company.store_limit`) via tenant-workspace APIs. Allocations must never exceed
the Tenant entitlement.

Companies can only create (or reactivate) Stores within their allocated allowance
**and** while the Tenant still has remaining entitlement. Enforcement lives in
`backend/app/store_entitlements.py` and is called from `stores.create_store` /
store activation — never frontend-only.

### Permanent rules

1. **Backend enforcement is mandatory.** Disabling a UI button is not sufficient.
2. **Never delete business data** because a subscription is downgraded. Preserve
   Stores, sales, inventory, payments, accounting, reports, and audit history.
   While over entitlement, block new creates / reactivation; surface
   `over_entitlement` on the tenant dashboard.
3. **Tenant isolation** remains shared-schema + `tenant_id` (ADR-001). Stores
   belong to one Company and therefore one Tenant.
4. **Unlimited** uses integer `-1` (enterprise catalog `None` maps to `-1`).
5. **Live billing / checkout Completes remain deferred** (ADR-002). Caps are real
   gates on tenant columns, not fabricated MRR.
6. **User↔store membership** remains deferred (ADR-005). Do not invent parallel
   membership tables unless that ADR is intentionally opened. Until then, store
   manager operational scope uses ``stores.manager_id`` via
   `backend/app/dashboard_scope.py` (`managed_store_ids`, `constrain_store_query`,
   `assert_transfer_touches_manager_scope`, `managed_warehouse_ids`,
   `constrain_warehouse_query`, `apply_warehouse_scope_filter`,
   `apply_purchase_invoice_warehouse_scope`, `STORE_SCOPE_DENIED`) — dashboard/BI,
   POS sales, sales invoices, expenses, stores, transfers, warehouse inventory ops,
   purchasing PR/PO/GRN/returns, purchase invoices (direct `warehouse_id` or linked
   PO/GRN warehouse), sales orders, POS sessions, low-stock / expiring-batch
   list+export+reports, inventory balance/valuation/movements reports, sales
   daily/monthly/products/customers/salesperson/by-store reports, purchasing
   summary/suppliers/pending/returns reports, transfer history report,
   inventory stock-transfer write asserts (from-WH required; mutations must touch
   managed stores), expenses summary + category budget spent/pending
   (null-store fail-closed; budget limits company-level — create/patch denied for store_manager; spend/pending still scoped), expense +
   recurring create / expense patch store asserts (foreign `store_id` denied),
   and AI inventory low-stock / demand-forecast / dead-stock / predictions
   (+ exports; chat stockout intent) via managed WarehouseStock + store sales
   (null-store fail-closed; empty managed WH → empty; no `product.stock_qty`
   fallback), and AI insights + sales/expenses/purchases/cross-domain analysis
   (+ exports) with the same store/WH fail-closed semantics, AI customer
   insights/assist (+ export; chat customer count) from managed-store sales
   only (customer universe = buyers on those invoices), AI chat
   top-product / sales-month / expenses / classic low-stock helpers
   (managed-store invoices/expenses; managed WarehouseStock vs reorder —
   not `product.stock_qty`; empty managed store/WH → empty/zero), AI
   security alerts (+ export) fail-closed to self-attributed audit events
   plus details.store_id/warehouse_id in managed scope (no audit store
   column), and AI documents/analyze (+ export) match only customers on
   managed-store sales, suppliers on managed-WH PO/GRN/PI, and products
   with managed WH stock or managed-store sales (expense categories remain
   company-level), and credit AR/AP aging (+ export; dashboard credit slice;
   BI credit; reports credit_aging export) from managed-store invoices /
   managed-WH purchase bills (null-store/null-WH fail-closed; party ledger
   balance zeroed under scope), and credit statements / outstanding /
   payment registers (+ exports) plus customer/supplier payment write
   asserts (invoice/PO/PI required in managed scope; unallocated payments
   denied), and accounting P&L / trial balance / cash-flow / balance-sheet
   (+ path CSVs, `/reports/export`, dashboard MTD P&L) from managed-store
   journals (null-store fail-closed; foreign `store_id` denied), and tax
   report / filing (+ path CSV, `/reports/export` tax/tax_filing*) from
   managed-store sales/POS + managed-WH purchase bills/POs (null-store /
   null-WH fail-closed; empty managed → zero), and audit list/export
   fail-closed to self-authored events plus details with managed
   `store_id`/`warehouse_id` (no audit store column; ADR-005 open), sales
   returns via linked invoice store (+ export/asserts), and dashboard
   expenses / stock-alerts / summary (+ main dashboard inventory KPIs /
   pending expenses) store+WH scoped (not `product.stock_qty`), and
   accounting journal entries (+ export; create/unpost/attachment asserts)
   from managed-store journals (null-store fail-closed; foreign `store_id`
   denied), and sales invoice create/post/send/cancel + CSV export (+ get/print
   null-store fail-closed) store scoped + **credit_limit_override denied for
   store_manager on invoice post / POS credit** (default role has credit:approve;
   override remains company/finance admin), and recurring expense list/export/
   patch/generate residual store scoped (null-store fail-closed), and COA
   account ledger (+ export) from managed-store journals (null-store
   fail-closed), and bank statements list/export/get/reconcile writes
   (+ create/import) scoped to managed liquid accounts, and bank connections
   list/export/create/patch/delete/sync scoped to managed liquid accounts,
   and expense approve/reject/delete + OCR suggest/apply +
   attachment upload/delete writes store scoped, and customer/supplier
   history (+ CSV) store+WH scoped (open quotations omit without store
   column), and per-product batches list/export WH scoped (null-WH
   fail-closed), and cheques list/get/export/lifecycle via payment
   invoice store / WH scope (null/unallocated fail-closed), and POS
   holds list/create/resume/discard via `PosSession.store_id` (null
   session fail-closed) + drawer-settings CSV export store scoped, and
   stores CSV export + patch/drawer/reorder write asserts (create denied
   for store_manager), and notifications list/export/unread/mark +
   scan-due (payment/recurring) via entity store/WH joins (quotations
   omitted/skipped — no store_id), and products catalog list/get/export/
   lookup/POS search stock_qty from managed WarehouseStock (not
   product.stock_qty), and sales quotations list/export/get/lifecycle
   via own drafts + converted in-scope order/invoice (no store_id), and
   **branches/departments create/patch denied for store_manager** (company-level
   org units; reads/export allowed even with users:write), and **catalog
   categories/brands/units create/patch/deactivate (+ brand logo writes) denied
   for store_manager** (company-level catalog meta; list/export/convert reads
   allowed), and **customer groups create/patch/deactivate denied for
   store_manager** (company-level sales master; list/export/get reads allowed),
   and **product CSV import denied for store_manager** (company-level catalog
   master bulk seed; template/export reads allowed), and **product catalog
   master writes denied for store_manager** (create/patch + variants + barcode
   assign + image writes; list/get/export/lookup/POS search reads + WH stock
   ops remain), and **stock CSV import denied for store_manager** (company-level
   bulk WH / product.stock_qty seed; template read + per-WH stock-in/out remain),
   and **customer/supplier deactivate denied for store_manager** (company-level
   party master lifecycle; create/list/get + non-credit patch remain), and
   **party payment_terms_days create/patch denied for store_manager** (credit-
   adjacent company terms; zero-default create allowed; phone/name patch remain),
   and **AI report template create/delete denied for store_manager** (company-
   level NL report templates; list/export reads allowed), and **AI NL report
   generate/export denied for store_manager** (company-level ``/ai/reports/generate``;
   store-scoped ``/reports/*`` + Layer-1 AI insights remain), and **customer/supplier
   contact create/delete denied for store_manager** (company-level party contact
   master; get/list reads remain; nested contacts on create remain allowed), and
   **company membership assign/revoke denied for store_manager** (even when
   companies write is granted; list/read remain when permitted).
   and **company profile/logo branding writes denied for store_manager** (even when
   companies write is granted; company GET remains when permitted),
   and **business-insights settings PUT denied for store_manager**
   (company-level BI thresholds/formulas; GET settings/formulas + acknowledge/dismiss remain),
   and **purchasing PR approval settings PATCH denied for store_manager**
   (company-level approval matrix; GET/export remain; admin allowlist retained),
   and **legacy POST /sales and /purchases denied for store_manager** (unscoped
   Transaction writes; use store-scoped invoices / purchasing pipeline), and
   **store manager_id assign/clear denied for store_manager** (company-level
   manager assignment; other managed-store patches remain), and **store
   branch_id assign/clear denied for store_manager** (company-level store↔branch
   org link; other managed-store patches remain), and **warehouse manager_id
   assign/clear denied for store_manager** (company-level WH manager assignment;
   other managed-WH patches remain), and **warehouse store_id assign/clear
   denied for store_manager** (company-level WH↔store org link; other managed-WH
   patches remain), and **company store-limit allocation denied for
   store_manager** (tenant entitlement allocation; even when companies write
   granted; tenant-admin path retained).
   Not store-scoped RBAC Complete.
7. Reuse `stores` RBAC module actions (`read`/`write`) and tenant-admin roles for
   allocation; do not invent dotted permission strings unless the RBAC system is
   extended project-wide.
8. **Offline soft lockdown is PARTIAL:** revoke expires server `offline_authorized_until`
   and blocks sync; critical alerts can email via security notifications
   (`POST /offline/alerts/notify`). Remote IndexedDB wipe, push delivery, Offline
   Complete, and 7-day VERIFIED remain MISSING.

### Key modules

| Concern | Module |
|---------|--------|
| Entitlement math + locks | `backend/app/store_entitlements.py` |
| Store create/activate | `backend/app/stores.py` |
| Tenant dashboard payload | `backend/app/companies.py` |
| Plan catalog soft limits | `backend/app/tenants.py` (`PLAN_CATALOG`) |
| Platform override API | `PATCH /api/v1/platform/tenants/{id}/store-entitlement` |
| Tenant allocation API | `PATCH /api/v1/companies/{id}/store-limit` |

### Do not claim Completes

Offline Complete, paid billing Completes, ADR-005 membership Completes, go-live,
and attestation Completes remain **MISSING** unless separately delivered with
evidence. Store, company, and user caps are subscription gates on `Tenant.max_*`
columns — not checkout or MRR Completes.

## Subscription Company Entitlement

RIBDIGI HOUSE controls the maximum company entitlement for a Tenant
(`Tenant.max_companies`, optional `Tenant.max_companies_override`, synced from
`PLAN_CATALOG.soft_limits.companies` when a plan changes and no override is set).

Tenants can only create Companies while under the effective entitlement.
Enforcement lives in `backend/app/workspace.py` (`assert_can_create_company`) and
is called from `companies.create_company` — never frontend-only.

### Permanent rules

1. **Backend enforcement is mandatory.** Disabling a UI button is not sufficient.
2. **Never delete Companies** (or their Stores, sales, inventory, payments,
   accounting, reports, or audit history) because a subscription is downgraded.
   While over entitlement, block new creates; surface `over_entitlement` via
   `company_entitlement` on the tenant dashboard.
3. **Tenant isolation** remains shared-schema + `tenant_id` (ADR-001).
4. **Unlimited** uses integer `-1` (enterprise catalog `None` maps to `-1`).
5. **Live billing / checkout Completes remain deferred** (ADR-002). Caps are real
   gates on tenant columns, not fabricated MRR.
6. When `max_companies_override` is set, plan changes do not overwrite
   `Tenant.max_companies` until the override is cleared.
7. Reuse `companies` RBAC module actions and tenant-admin workspace flows; do not
   invent parallel entitlement tables.

### Key modules

| Concern | Module |
|---------|--------|
| Entitlement math + counts | `backend/app/store_entitlements.py` |
| Create gate | `backend/app/workspace.py` (`assert_can_create_company`) |
| Company create | `backend/app/companies.py` |
| Tenant dashboard payload | `backend/app/companies.py` (`company_entitlement`) |
| Plan catalog soft limits | `backend/app/tenants.py` (`PLAN_CATALOG`) |
| Plan change sync | `backend/app/platform_api.py` (`apply_plan_company_defaults`) |
| Platform override API | `PATCH /api/v1/platform/tenants/{id}/company-entitlement` |
| Platform override UI | `frontend/app/platform/tenants/[id]/page.tsx` |
| Migration | `backend/alembic/versions/20260823_0107_company_entitlements.py` |
| Tests | `backend/tests/test_company_entitlements.py` |

## Subscription User Entitlement

RIBDIGI HOUSE controls the maximum active-user entitlement for a Tenant
(`Tenant.max_users`, optional `Tenant.max_users_override`, synced from
`PLAN_CATALOG.soft_limits.users` when a plan changes and no override is set).

User create, bulk import, and reactivation are blocked at the limit
(`USER_LIMIT_REACHED`). Enforcement lives in `backend/app/store_entitlements.py`
(`assert_can_create_user`, `assert_can_reactivate_user`) and is called from
`api.py` user-create/reactivate paths and `user_import.py` — never frontend-only.

Alembic `20260823_0108` (`tenants.max_users_override`) is on branch tip; apply
after `0107` in deploy order.

### Permanent rules

1. **Backend enforcement is mandatory.** Disabling a UI button is not sufficient.
2. **Never delete Users** because a subscription is downgraded. Deactivate if
   needed; block new creates and reactivations while over entitlement; surface
   `over_entitlement` via `user_entitlement` on the tenant dashboard.
3. **Tenant isolation** remains shared-schema + `tenant_id` (ADR-001). User caps
   count active `User` rows for the tenant — not per-store membership (ADR-005).
4. **Unlimited** uses integer `-1` (enterprise catalog `None` maps to `-1`).
5. **Live billing / checkout Completes remain deferred** (ADR-002). Caps are real
   gates on tenant columns, not fabricated MRR.
6. When `max_users_override` is set, plan changes do not overwrite
   `Tenant.max_users` until the override is cleared.
7. **User↔store membership** remains deferred (ADR-005). Do not invent parallel
   membership tables unless that ADR is intentionally opened.

### Key modules

| Concern | Module |
|---------|--------|
| Entitlement math + gates | `backend/app/store_entitlements.py` |
| User create / reactivate | `backend/app/api.py` |
| Bulk import gate | `backend/app/user_import.py` |
| Tenant dashboard payload | `backend/app/companies.py` (`user_entitlement`) |
| Plan catalog soft limits | `backend/app/tenants.py` (`PLAN_CATALOG`) |
| Plan change sync | `backend/app/platform_api.py` (`apply_plan_user_defaults`) |
| Platform override API | `PATCH /api/v1/platform/tenants/{id}/user-entitlement` |
| Tenant dashboard UI | `frontend/app/tenant/page.tsx` |
| Migration | `backend/alembic/versions/20260823_0108_user_entitlements.py` |
| Tests | `backend/tests/test_user_entitlements.py` |

## Smart Business Intelligence (Layer 1)

Deterministic, offline-capable insights engine. **No OpenAI / Gemini / Anthropic /
external LLM.** Calculations use Ribdigi ERP DB data only (sales, inventory,
purchases, expenses, credit, expiry, etc.) with tenant/company/store RBAC.

| Concern | Module |
|---------|--------|
| Orchestrator | `backend/app/bi_service.py` (`BusinessIntelligenceService`) |
| Metrics | `backend/app/bi_metrics.py` (`BusinessMetricsService`) |
| Rules | `backend/app/bi_rules.py` (`InsightRulesService`) |
| Priority | `backend/app/bi_priority.py` |
| Recommendations | `backend/app/bi_recommendations.py` |
| Defaults / formulas | `backend/app/bi_defaults.py` |
| API | `backend/app/bi_api.py` → `/api/v1/business-insights/*` |
| UI | `frontend/app/business-insights/page.tsx` |
| Migration | `backend/alembic/versions/20260816_0105_business_insights.py` |
| Tests | `backend/tests/test_business_intelligence.py` |

RBAC module: `business_insights` (`read` / `write`). Financial/credit sections
also require existing `accounting`/`reports`/`credit` permissions. Layer 2
generative AI adapters are out of scope; Layer 1 must remain fully usable alone.
