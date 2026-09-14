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
   PO/GRN warehouse), sales orders, POS sessions (open requires managed
   ``store_id``; null/unset fail-closed), low-stock / expiring-batch
   list+export+reports, inventory balance/valuation/movements reports (**cost/value redacted** for store_manager) + **stock-count variance unit_cost/variance_value redacted** (JSON/CSV/PDF; qty remain), sales
   daily/monthly/products/customers/salesperson/by-store reports, purchasing
   summary/suppliers/pending/returns reports, transfer history report,
   inventory stock-transfer write asserts (from-WH required; mutations must touch
   managed stores) + **stock-transfer from_store_manager_id/to_store_manager_id
   redacted** on stores/inventory transfer JSON + transfer history (store/WH ids
   remain; managed-store list ``manager_id`` self-scope remains), expenses summary + category budget spent/pending
   (null-store fail-closed; budget limits company-level — create/patch + categories list denied for store_manager; budget_amount/variance/utilization + category master id/code/account_id redacted on budgets JSON/CSV + embeds; spend/pending/name still scoped), expense +
   recurring create / expense patch store asserts (foreign `store_id` denied;
   **expense department_id assign/clear denied + department_id redacted** on
   expense/recurring list/get/export/patch JSON/CSV; **expense category_id
   redacted** on expense/recurring list/get/patch JSON + OCR/AI embeds —
   free-text category name remains),
   and AI inventory low-stock / demand-forecast / dead-stock / predictions
   (+ exports; chat stockout intent) via managed WarehouseStock + store sales
   (null-store fail-closed; empty managed WH → empty; no `product.stock_qty`
   fallback; **dead-stock cost_price / carrying-cost redacted** on JSON + CSV), and AI insights + sales/expenses/purchases/cross-domain analysis
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
   balance zeroed under scope; **party ``credit_limit`` redacted** on aging
   JSON), and credit statements / outstanding /
   payment registers (+ exports; **customer statement party ``credit_limit``
   redacted**) plus customer/supplier payment write
   asserts (invoice/PO/PI required in managed scope; unallocated payments
   denied), and accounting P&L / trial balance / cash-flow / balance-sheet
   (+ path CSVs, `/reports/export`, dashboard MTD P&L) from managed-store
   journals (null-store fail-closed; foreign `store_id` denied), and tax
   report / filing (+ path CSV, `/reports/export` tax/tax_filing*) from
   managed-store sales/POS + managed-WH purchase bills/POs (null-store /
   null-WH fail-closed; empty managed → zero) + **tax rate create/patch/default
   + list/detail GET + CSV export denied** + **``/tax/calculate`` company master
   resolve denied** (``tax_rate_id`` / default-rate fallback; explicit
   rate/components math remains) + **tax filing TIN redacted** (``tax_registration_number``
   on ``/reports/tax/filing`` JSON + government header + ``tax_filing_*`` exports;
   amounts/schedules remain), and audit list/export
   fail-closed to self-authored events plus details with managed
   `store_id`/`warehouse_id` (no audit store column; ADR-005 open), sales
   returns via linked invoice store (+ export/asserts), and dashboard
   expenses / stock-alerts / summary (+ main dashboard inventory KPIs /
   pending expenses) store+WH scoped (not `product.stock_qty`), and
   accounting journal entries (+ export; create/unpost/attachment asserts;
   **list/get/create/unpost/upload/delete ``attachment_url`` storage key redacted**)
   from managed-store journals (null-store fail-closed; foreign `store_id`
   denied), and sales invoice create/post/send/cancel + CSV export (+ get/print
   null-store fail-closed) store scoped + **credit_limit_override denied for
   store_manager on invoice post / POS credit** (default role has credit:approve;
   override remains company/finance admin) + **CREDIT_LIMIT_EXCEEDED 409 ``credit_limit`` / ``available`` / ``current_balance`` / ``projected_balance`` redacted** (invoice post / POS credit; ``exceeded`` / ``code`` / ``message`` / ``additional_amount`` remain; admin keeps projection) + **sales invoice credit-override audit redacted** (``credit_limit_overridden`` / ``credit_override_reason`` / ``by`` / ``at``; balance/status remain) + **sales invoice emailed_to redacted** (``delivery.to`` on send; ``emailed_at`` remains) + **quotation emailed_to redacted** (list/get/send/print/export + ``delivery.to``; ``emailed_at`` remains) + **purchase-order emailed_to redacted** (list/get/create/patch/amend/send/print/cancel/export + convert/low-stock + ``delivery.to``; ``sent_at`` remains), and recurring expense list/export/
   patch/generate residual store scoped (null-store fail-closed), and COA
   account ledger (+ export) from managed-store journals (null-store
   fail-closed), and bank statements list/export/get/reconcile writes
   (+ create/import) scoped to managed liquid accounts, and bank connections
   list/create/patch/delete/sync scoped to managed liquid accounts
   (+ CSV export denied; feed identity redacted on list/patch)
   (**bank connection is_active lifecycle writes denied for store_manager**;
   display name patches on managed connections remain; sync policy + credential
   field patches also denied),
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
   product.stock_qty; cost_price redacted on list/get/export + per-product variants; category_id/brand_id/unit_id/tax_rate_id redacted on list/get + category_code/brand_code/unit_code blanked on export; **sales-by-product report/export category_id redacted** (revenue/qty/name/product_id/sku remain; categories list GET + product list/get assignment already denied/redacted) + **sales-by-product category_id query/export filter denied** (`STORE_SCOPE_DENIED`; unfiltered report remains; admin may filter); **inventory balance/valuation cost_price/value/total_value redacted** on JSON + `/reports/export`; **low-stock list/export cost_price redacted**; **AI dead-stock cost_price/estimated_carrying_cost/total_carrying_cost redacted** on JSON + CSV; **stock-count variance unit_cost/variance_value/total_variance_value redacted** on JSON/CSV/PDF), and sales quotations list/export/get/lifecycle
   via own drafts + converted in-scope order/invoice (**quotation ``emailed_to`` redacted**; ``emailed_at`` remains), and purchasing orders
   (**purchase-order ``emailed_to`` redacted**; ``sent_at`` remains), and
   **branches/departments create/patch/list GET/export denied for store_manager** (company-level
   org units) + **users list/get denied for store_manager** (company org roster dump after
   users CSV export deny; self ``/me`` remains; PII/org/MFA redacts retained defense-in-depth), and **catalog
   categories/brands/units create/patch/deactivate (+ brand logo writes) denied
   for store_manager** (company-level catalog meta; list/export/convert + brand
   logo binary GET denied; product reads + WH stock ops remain), and **customer groups create/patch/deactivate denied for
   store_manager** (company-level sales master; list/export/get reads allowed),
   and **product CSV import denied for store_manager** (company-level catalog
   master bulk seed; import template denied) + **product catalog CSV export denied**
   (``GET /products/export`` company roster dump; list/get + WH stock ops remain), and **product catalog
   master writes denied for store_manager** (create/patch + variants + barcode
   assign + image writes; list/get/lookup/POS search reads + WH stock
   ops remain) + **product images gallery list GET + CSV export denied**
   (``storage_key`` media dump) + **product primary image binary GET denied**
   (``GET /products/{id}/image``; WH stock ops remain;
   company/tenant logo binary GET stays open) + **print/receipt JSON
   ``logo_data_url`` redacted** (invoice/quotation/credit-note print + POS
   receipt; ``has_logo`` + server-side HTML/PDF embeds remain) + **print/receipt JSON
   ``legal_name`` / ``trading_name`` redacted** (invoice/quotation/credit-note print
   + POS receipt; ``company_name`` falls back to trading switcher when distinct;
   ``has_logo`` + server-side HTML/PDF/text embeds remain) + **POS receipt JSON
   ``company_address`` / ``company_phone`` redacted** (``company_name`` + ``has_logo``
   + server-side text/PDF embeds remain)    + **print/receipt JSON ``company_email``
   redacted** (invoice/quotation/credit-note print + POS receipt; ``company_name``
   + ``has_logo`` + server-side text/PDF/HTML embeds remain) + **print/receipt JSON
   ``tax_registration_number`` redacted** (invoice/quotation/credit-note print + POS
   receipt; ``company_name`` + ``has_logo`` + server-side text/PDF/HTML embeds remain)
   + **POS receipt JSON
   ``document_header`` / ``document_footer`` redacted** (``company_name`` + ``has_logo``
   + server-side text/PDF embeds remain) + **POS receipt JSON
   ``receipt_print_template`` / ``default_paper`` redacted** (``company_name`` + ``has_logo``
   + resolved ``paper`` + server-side text/PDF embeds remain) + **POS receipt JSON
   ``cashier_name`` redacted** (``company_name`` + ``has_logo`` + totals remain;
   server-side text/PDF embeds may retain name) + **POS receipt JSON
   ``currency`` redacted** (``company_name`` + ``has_logo`` + totals remain;
   server-side text/PDF embeds may retain code; ``/me`` switcher already omits
   company ``currency``) + **``/me`` + ``/workspace`` switcher
   ``business_type_label`` / ``industry`` omitted** (``GET /business-types`` already denied;
   id/name/has_logo remain) + **product
   list/get ``image_url``
   storage key redacted** + **product list/get ``has_image`` forced false**
   (admin list/get keep ``image_url`` + ``has_image``; WH stock ops / POS remain)
   + **expense list/get/patch ``attachment_url`` storage key redacted**
   (``has_attachment`` + store-scoped binary download remain; admin keeps key)
   + **purchase-invoice list/get/patch/upload ``attachment_url`` storage key redacted**
   (``has_attachment`` + WH-scoped binary download remain; admin keeps key)
   + **journal-entry list/get/create/unpost/upload/delete ``attachment_url`` storage key redacted**
   (``has_attachment`` + store-scoped binary download remain; admin keeps key;
   opening-balance / liquid-transfer JE responses included)
   + **product variants CSV export denied**
   (company roster ``/products/variants/export`` + per-product path
   ``/products/{id}/variants/export``; variants list/get remain for POS/sales), and **stock CSV import denied for store_manager** (company-level
   bulk WH / product.stock_qty seed; template read + per-WH stock-in/out remain),
   and **customer/supplier deactivate denied for store_manager** (company-level
   party master lifecycle; PATCH status also denied; create/list/get + non-credit
   patch remain), and
   **party payment_terms_days create/patch denied for store_manager** (credit-
   adjacent company terms; zero-default create allowed; name/notes patch remain)
   + **party credit master redacted on list/get/patch JSON** (credit_limit /
   payment_terms_days / early-pay null; balance/name remain; POS credit checks
   server-side) + **AI customer insights/assist/export credit_limit redacted**
   (nested customer rows + balance-answer text; monetary/churn remain) + **AI
   customer insights/assist/export party ``code`` redacted** (list/get code
   already redacted; name/monetary/churn remain),
   and **AI report template create/delete denied for store_manager** (company-
   level NL report templates; list/export reads allowed), and **AI NL report
   generate/export denied for store_manager** (company-level ``/ai/reports/generate``;
   store-scoped ``/reports/*`` + Layer-1 AI insights remain), and **company report
   schedule CRUD/run denied for store_manager** (even when ``reports:write`` granted;
   admin allowlist retained; store-scoped ``/reports/*`` reads remain), and
   **customer/supplier
   contact create/delete denied for store_manager** (company-level party contact
   master; nested contacts on create denied) + **party contacts roster
   redacted** on customer/supplier list/get/patch JSON (contacts → `[]`;
   name/status remain), and
   **company membership assign/revoke denied for store_manager** (even when
   companies write is granted; list/read remain when permitted).
   and **company profile/logo branding writes denied for store_manager** (even when
   companies write is granted; company GET remains when permitted),
   and **business-insights settings GET/PUT + formulas GET denied for store_manager** (overview/attention embeds + health weights redacted)
   + **BI overview profit COGS / stock_value / expiry value_at_risk redacted** (revenue/expenses/qty remain; engine still uses cost server-side)
   (company-level BI thresholds/formulas; GET settings/formulas + acknowledge/dismiss remain),
   and **purchasing PR approval settings GET/PATCH/export denied for store_manager**
   (company-level approval matrix; admin allowlist retained) + **expense/PR
   ``awaiting_roles`` redacted** on pending expense + purchase-request JSON
   (settings GET already denied; step/level counters remain) + **early-discount
   quote matrix redacted** (``discount_pct`` / ``window_days`` / ``source`` null
   after credit early-pay settings GET deny; eligible/discount_amount/cash_to_settle remain)
   + **supplier payment-schedule ``early_pay`` pack + nested quote matrix redacted**
   (``early_pay`` → ``{}``; nested ``discount_pct`` / ``window_days`` / ``source`` null;
   totals/buckets + eligible/discount_amount/cash_to_settle remain),
   and **document numbering / print-template / tenant profile PATCH /tenants/me
   denied for store_manager** (company-level document settings; admin export reads
   remain),
   and **legacy POST /sales and /purchases denied for store_manager** (unscoped
   Transaction writes; use store-scoped invoices / purchasing pipeline), and
   **store manager_id assign/clear denied for store_manager** (company-level
   manager assignment; other managed-store patches remain; managed-store list
   ``manager_id`` self-scope remains) + **stock-transfer from/to store
   manager_id redacted** on transfer JSON + history (peer org graph), and **store
   branch_id assign/clear denied for store_manager** (company-level store↔branch
   org link; other managed-store patches remain; branch_id redacted on
   list/export/patch JSON/CSV), and **warehouse manager_id
   assign/clear denied for store_manager** (company-level WH manager assignment;
   other managed-WH patches remain; manager_id redacted on list/export/patch
   JSON/CSV), and **warehouse store_id assign/clear
   denied for store_manager** (company-level WH↔store org link; other managed-WH
   patches remain), and **warehouse type/capacity structure writes denied for
   store_manager** (company inventory-master attributes; name/address on managed
   WH remain; warehouse_type/capacity redacted on list/export/patch JSON/CSV), and **warehouse is_active lifecycle writes denied for
   store_manager** (activate/deactivate admin-only; name/address remain), and
   **store is_active lifecycle writes denied for store_manager**
   (activate/deactivate admin-only / entitlement-gated; name/phone/address/
   operating_hours remain), and **opening stock writes denied for
   store_manager** (company fiscal inventory init / BR-5.2; stock-in/out on
   managed WH remain), and **inventory barcode labels WH-scoped for
   store_manager** (products without managed WarehouseStock denied; in-scope
   print remains), and **POS hold expire-stale denied for store_manager**
   (company maintenance; list/create/resume auto-expire own holds remain), and
   **liquid account is_active lifecycle writes denied for store_manager**
   (activate/deactivate admin-only; name on managed liquid accounts remain), and
   **bank connection is_active lifecycle writes denied
   for store_manager** (activate/deactivate admin-only; display name patches on
   managed connections remain), and **party customer_group assignment
   denied for store_manager** (company sales-master party↔group link; name/notes
   party patches remain) + **party customer_group redacted on list/get/patch**
   (customer_group_id/customer_group/customer_group_name/group_discount_percent
   null for store_manager; POS/sales apply discount server-side), and **bank connection create/delete denied for
   store_manager** (company bank-feed credentials; list/patch/sync on
   managed liquid accounts remain; **CSV export denied**; **feed_url/
   external_account_id redacted** on list/patch), and **bank connection credential field
   patches denied for store_manager** (access_token/feed_url/provider/external
   id; display_name on managed connections remain), and **bank connection sync
   policy patches denied for store_manager** (auto_sync/auto_match_after_sync/
   sync_lookback_days; display_name + manual sync on managed connections
   remain), and
   **offline device bind store-scoped for store_manager** (managed store_id
   required; foreign/unset fail-closed; device register/revoke remain admin), and
   **offline sync push/pull/ack + conflicts/status store-scoped for store_manager**
   (managed ``store_id`` required on `/sync/push` + `/sync/pull` + `/sync/ack`;
   conflicts/status limited to managed-store-bound devices; null device fail-closed;
   Offline Complete remains MISSING), and
   **liquid account bank detail patches denied for store_manager**
   (bank_name/account_number/bank_branch/clear_bank_details; name on managed
   liquid accounts remain), and
   **party category/party_type classification writes denied for store_manager**
   (company party master classification; name remain) + **party category/party_type
   redacted on list/get/patch JSON**, and **party master
   code writes denied for store_manager** (customer/supplier ``code`` on
   create/patch; name remain; create without code allowed) + **party master
   code redacted on list/get/patch JSON**, and
   **party master email writes denied for store_manager** (customer/supplier
   ``email`` on create/patch; name remain; create without email allowed;
   nested contact endpoints remain separately denied), and
   **party master phone writes denied for store_manager** (customer/supplier
   ``phone`` on create/patch; name remain; create without phone
   allowed), and
   **party master address/geo writes denied for store_manager** (customer/supplier
   ``address``/``latitude``/``longitude`` on create/patch; name remain;
   create without address allowed), and
   **party master notes writes denied for store_manager** (customer/supplier
   ``notes`` on create/patch; name remain; create without notes allowed), and
   **party master CSV export denied for store_manager** (customers/suppliers
   ``/export`` company CRM dump; list/get + scoped history CSV remain), and
   **party status lifecycle patches denied for store_manager** (PATCH status
   cannot bypass DELETE deactivate deny; name remain), and **POS session
   open requires managed store_id for store_manager** (null/unset fail-closed;
   foreign store denied; list/report remain store scoped), and **POS session
   close/drawer/report/current null-store fail-closed for store_manager**
   (``assert_pos_session_store_in_manager_scope``; foreign store still denied),
   and
   **company store-limit allocation denied for store_manager** (tenant
   entitlement allocation; even when companies write granted; tenant-admin path
   retained).
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

## PR #303 store_manager RBAC continuum (honesty source of truth)

**Branch:** `cursor/transfer-genemonyuglaze-gate-427f` (PR #303).  
**As of tip:** `aed70d3b804d63c501178d748008664e06bc7400` — `feat(rbac): redact credit payment currency for store_manager` (feat ancestry credit-payment `currency` `450f6476d7` + tax-filing jurisdiction `8d34911703` + credit-aging document currency `f191a48c68` + purchase-invoice `currency` `2ae6d54e66` + sales-invoice `currency` `4991a65408` + CREDIT_LIMIT_EXCEEDED ledger `d18464cc85` + tax-filing prefs `420cefc891` + sales-products category filter `b62deba73f` + sales-products `category_id` `10d5ca80ec` + schedule `early_pay` `65804e2e17` + `/me` tenant prefs `2aebf47cb4` + POS receipt `currency` `b1115a3e78` + CREDIT_LIMIT_EXCEEDED `e1a5371160` + statement `credit_limit` `4c7fbf7362` + credit-aging `1130099b1e` + sales-customers `code` `8afdad1154` + switcher catalog omit `fb9cc51f37` + POS receipt `cashier_name` `09da411c82` + sales-salesperson `role` `0c56a2c5a0` + `full_name` `e4df69d520` + `email` `a4c2aeb4bf` + stock-movement `created_by_name` `1e3560b847` + `created_by_email` `f6921faffb` + print/receipt TIN `5eb2864692` + company_email `73752ad7e2` + invoice print `template` `5d076753b7` + receipt print template `8d06c785d9` + tax filing TIN `47844e3c4d` + continuum PO `emailed_to` `9ff88796a1` + security H1–H5 `3cf99a5540`/`caf7d98b55`)...
**Honesty:** **PARTIAL** only — never Offline Complete, never 7-day VERIFIED, never go-live, never paid billing Complete, never ADR-005 membership Complete, never store-scoped RBAC Complete.

Keep this section, `docs/COMMERCIAL_READINESS_REPORT_2026-08-23.md` tip banner, and
`/opt/cursor/artifacts/pr303_body_update.md` synchronized on the same tip SHA and
the same leftovers list. Prefer bumping “as of” after each landed slice; do not
leave contradictory Complete/PARTIAL wording across those three surfaces.

### Intentionally still open (do not rewrite as closed)

1. Company/tenant **logo binary GET** (workspace chrome; branding *writes* already denied). Mistaken close in `b0fc721a15` was **reverted** — leftover restored.
2. Per-user `/auth/sessions` + `/notifications/settings` (self-service; not company dumps).
3. **ADR-005** user↔store membership **MISSING** (`stores.manager_id` scope remains).
4. Managed-store list may still expose self-scope `manager_id` (not peer org graph).

### Closed continuum themes (summary — still PARTIAL)

Defense-in-depth on tip ancestry includes: store/WH ops + report/export scoping;
company-level admin / settings / catalog / party-master / bank-feed / offline-device
denies; JSON/CSV redacts for cost, PII, org links, approval-matrix `awaiting_roles`,
early-discount quote matrix fields, and BI company config/cost embeds; product
images gallery list GET; product variants path CSV export (after roster export
deny); product catalog CSV export (`GET /products/export`); users list/get
(company org roster after users CSV export deny); product primary image binary
GET (`GET /products/{id}/image`); product list/get `image_url` storage-key
redact; product list/get `has_image` forced false; expense list/get/patch
`attachment_url` storage-key redact (`has_attachment` + scoped binary download
remain); purchase-invoice list/get/patch/upload `attachment_url` storage-key
redact (`has_attachment` + WH-scoped binary download remain); journal-entry
list/get/create/unpost/upload/delete `attachment_url` storage-key redact
(`has_attachment` + store-scoped binary download remain); print/receipt JSON
`logo_data_url` redact (invoice/quotation/credit-note print + POS receipt;
`has_logo` + server-side HTML/PDF embeds remain); print/receipt JSON `legal_name` / `trading_name` redact (invoice/quotation/credit-note print + POS receipt; `company_name` falls back to trading switcher when distinct; `has_logo` + server-side HTML/PDF/text embeds remain); POS receipt JSON `company_address` / `company_phone` redact (`company_name` + `has_logo` + server-side text/PDF embeds remain); print/receipt JSON `company_email` redact (invoice/quotation/credit-note print + POS receipt; `company_name` + `has_logo` + server-side text/PDF/HTML embeds remain); print/receipt JSON `tax_registration_number` redact (invoice/quotation/credit-note print + POS receipt; `company_name` + `has_logo` + server-side text/PDF/HTML embeds remain); POS receipt JSON `document_header` / `document_footer` redact (`company_name` + `has_logo` + server-side text/PDF embeds remain); POS receipt JSON `receipt_print_template` / `default_paper` redact (`company_name` + `has_logo` + resolved `paper` + server-side text/PDF embeds remain); invoice/quotation/credit-note print JSON `template` / `invoice_print_template` redact (`company_name` + `has_logo` + server-side text/PDF/HTML embeds remain); tax filing TIN redact (`tax_registration_number` on `/reports/tax/filing` JSON + government header + `tax_filing_*` exports; amounts/schedules remain); **tax filing company prefs redacted** + **tax filing jurisdiction redacted** (`jurisdiction`/`supported_jurisdictions`/`government.jurisdiction`) (`tax_filing_period` + government header `currency`/`timezone`/`filing_period`; amounts/schedules/`taxpayer_name` remain; TIN already redacted; `/me` prefs + receipt currency already redacted); sales-invoice credit-override audit redact (`credit_limit_overridden` / `credit_override_reason` / `by` / `at`; balance/status remain); sales-invoice `emailed_to` redact (`delivery.to` on send; `emailed_at` remains); quotation `emailed_to` redact (list/get/send/print/export + `delivery.to`; `emailed_at` remains); purchase-order `emailed_to` redact (list/get/create/patch/amend/send/print/cancel/export + convert/low-stock + `delivery.to`; `sent_at` remains); stock-movement list/export `created_by_email` redact (qty/type/notes/`created_at` remain; users list/get already denied); stock-movement list `created_by_name` redact (qty/type/notes/`created_at`/`created_by` id remain; CSV columns omit name; users list/get already denied); sales-by-salesperson report/export staff `email` redact (revenue/sale_count/`user_id` remain; users list/get already denied); sales-by-salesperson report/export staff `full_name` redact (revenue/sale_count/`user_id` remain; email already redacted; users list/get already denied); sales-by-salesperson report/export staff `role` redact (revenue/sale_count/`user_id` remain; email/full_name already redacted; users list/get already denied); POS receipt JSON `cashier_name` redact (`company_name` + `has_logo` + totals remain; server-side text/PDF embeds may retain name; users list/get already denied); `/me` + `/workspace` switcher omit `business_type_label` / `industry` (`GET /business-types` already denied; id/name/has_logo remain); sales-by-customer report/export party `code` redact (revenue/sale_count/name/`customer_id` remain; party list/get + AI customer `code` already redacted); credit AR/AP aging party `credit_limit` redact (scoped `total_due`/buckets/name/documents remain; party list/get + AI `credit_limit` already redacted); customer AR statement JSON/CSV party `credit_limit` redact (scoped lines/name/zeroed balance remain; aging + party list/get + AI already redacted); CREDIT_LIMIT_EXCEEDED 409 `credit_limit`/`available` redact (invoice post / POS credit; `exceeded`/`code`/`message`/`additional_amount` remain; admin keeps projection; statement + aging + party list/get + AI already redacted); POS receipt JSON `currency` redact (`company_name` + `has_logo` + totals remain; server-side text/PDF embeds may retain code; `/me` switcher already omits company `currency`); GET `/me` tenant preference settings redact (`timezone` / `date_format` / `number_format` / `time_format` / `inactivity_timeout_minutes`; role/permissions/switcher chrome remain; `GET /tenants/me` already denied); supplier payment-schedule JSON `early_pay` pack + nested `early_discount` matrix redact (`early_pay` → `{}`; `discount_pct` / `window_days` / `source` null; totals/buckets + eligible/discount_amount/cash_to_settle remain; settings GET + party early-pay + dedicated quotes already denied/redacted).; sales-by-product report/export `category_id` redact (revenue/qty/name/`product_id`/`sku` remain; product list/get catalog assignment + categories list GET already denied/redacted); **sales-by-product `category_id` query/export filter denied** (`STORE_SCOPE_DENIED`; unfiltered remains; admin may filter); tax filing JSON/CSV company prefs redact (`tax_filing_period` + government header `currency`/`timezone`/`filing_period`; amounts/schedules/`taxpayer_name` remain; TIN already redacted; `/me` prefs + receipt currency already redacted); sales-invoice list/get/export/print `currency` redact (totals/status/balance/`exchange_rate` remain; company profile + `/me` switcher + POS receipt currency already omitted/redacted); **purchase-invoice list/get/export `currency` redact** (totals/status/balance/`exchange_rate` remain; sales-invoice + POS receipt + `/me` switcher currency already omitted/redacted). credit AR/AP aging document `currency` redact (JSON/CSV; `balance_due`/`balance_due_base`/`exchange_rate`/buckets/party name remain; sales/purchase-invoice + POS receipt `currency` already redacted; exchange-rates GET already denied).; **tax filing jurisdiction redacted** (`jurisdiction` / `supported_jurisdictions` / `government.jurisdiction`; amounts/schedules/`taxpayer_name` remain; TIN + company prefs already redacted).; **credit customer/supplier payment register JSON/CSV (+ create) `currency` redact** (amount/method/`exchange_rate`/`fx_gain_loss` remain; sales/purchase-invoice + aging document + POS receipt `currency` already redacted; exchange-rates GET already denied). Each slice closes
one dump or write path; the continuum as a whole stays **PARTIAL**.

### Continuum agent contract

1. **Flock before mutate:** `flock -w 300 /tmp/commercial_rbac_slice.lock` before
   product or honesty edits on this branch. Push honesty with
   `flock /tmp/git_push_honesty.lock`.
2. **One dump per slice:** land one focused deny/redact + tests; do not batch
   unrelated leftovers into the same commit.
3. **Honesty fields (same way every slice):** tip SHA + short subject; status
   **PARTIAL** only; refresh the three surfaces above; keep the intentionally-open
   list unless that exact leftover was the slice.
4. **PR body:** try `gh pr edit 303 --body-file …`; on failure, always refresh
   `/opt/cursor/artifacts/pr303_body_update.md` so the next agent has the intended body.
5. **Do not** claim Offline Complete, 7-day VERIFIED, go-live, paid billing Complete,
   or ADR-005 Complete. **Do not** rewrite unrelated leftovers as closed.

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
