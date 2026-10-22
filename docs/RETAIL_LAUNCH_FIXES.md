# Retail launch fixes

Audit of Ribdigi ERP for **retail shops, Help & Support, and the software-owner console**, done on 22 Oct 2026 against the local Docker stack (`ribdigi-erp-production`). Industry modules (hotel, hospital, restaurant, FMCG, pharmacy) are out of scope.

Shared tick-list version (same items): https://claude.ai/artifact/FejAxZsxg9NJxuYDx8uL51

## Recheck 22 Oct 2026, 19:30

Verified fixed in the working copy (not committed yet): 1.1, 1.2, 1.3, 1.4, 1.7, 1.8, 3.1, 3.3, 4.7.
Still open: 1.5 (phone sidebar arrow), 1.6 (credit race: a slow first `refresh()` with `kind === 'receivable'` sets the first customer as `partyId` after the switch to Payables — ignore stale refresh results or only load credit when `partyId` is in the current kind's list), all of section 2, 3.2 (8 tests left), 3.4 (`test_dokploy_source_revision` needs `git`; skip when missing), 4.1–4.6. 4.3: `/legal/terms` and `/legal/privacy` exist and login links to them, but the local dev server returns 404 until `next dev` is restarted — confirm after restart.

## Fixed 22 Oct 2026, ~21:00 (uncommitted, in this working copy)

- **1.1** `backend/app/stores.py` `warehouse_for_store`: prefers an active warehouse, then the store's own `WH-<store code>`, then code. New tests `backend/tests/test_store_warehouse_pick_r1.py`. Existing data: `backend/scripts/fix_duplicate_store_warehouses.py` (dry run; `--apply` unlinks extra warehouses and prints their stock).
- **1.5** `frontend/app/globals.css`: at ≤900px `.shell:not(.is-pos) > .main` keeps a 52px left gutter (the later padding shorthand had reset it).
- **1.6** `frontend/app/(dashboard)/credit/page.tsx`: a refresh started for one kind is ignored if the kind changed; in-flight dedupe is per kind; credit info loads only for a party in the current list.
- **3.2 / 3.4** last 8 screen-text tests point at current code; `test_dokploy_source_revision` skips when git or `.git` is missing.
- Checks run: till sales on a two-warehouse store, Credit switch (normal and fast), phone layout on 5 pages, updated tests (30 passed, 1 skipped), frontend `tsc --noEmit` clean.

## Recheck 22 Oct 2026, 20:05 (after restarting the local frontend)

- **1.1 re-opened.** No crash any more, and linking a second warehouse is refused. But for a store that *already* has two linked warehouses, `warehouse_for_store` now orders by `Warehouse.code` and returns the first: in the audit company that is `WH-BACK` (0 in stock) instead of `WH-MAIN` (68), so every till sale returns 409 `INSUFFICIENT_WAREHOUSE_STOCK` "Out of stock at this store". Fix: prefer a default/main warehouse (or the one holding stock), and add a one-off data fix that unlinks duplicate store links.
- **4.3 partly done.** `/legal/terms` and `/legal/privacy` now open (200) and are linked from login, but each is ~185 words of product notes. Still missing for a paid service: legal entity name and address, effective date, fees/renewal/refunds, liability limits, termination and data export, governing law (Ghana), data retention, and how you comply with Ghana's Data Protection Act, 2012 (Act 843). Have a lawyer review.
- Still open as before: 1.5, 1.6 (still 404 after the restart), section 2, 3.2, 3.4, 4.1, 4.2, 4.4–4.6.

## How to work through this file (for Cursor / the developer)

- Work top to bottom. Item 1 (POS crash) blocks launch.
- Follow `AGENTS.md`: new work on `main`, test, then merge to `production`. Never force-push.
- Keep each fix small and in the style of the surrounding code. Add or update a test for each code fix.
- Tick `[x]` when the **Check** step passes.
- Line numbers are from 22 Oct 2026 and may have moved; search for the quoted code if so.

---

## 1. Bugs to fix

### [x] 1.1 HIGH: till sales crash when a store has two warehouses
- **Problem:** If a store has two warehouses linked to it (the app allows linking a second one), every sale at that store's till returns 500 "The server could not complete this request." Reproduced with cash, card, mobile money and split payments.
- **Where:** `backend/app/stores.py:137` `warehouse_for_store()` calls `scalar_one_or_none()` and raises `sqlalchemy.exc.MultipleResultsFound`. Called from `backend/app/api.py:10196` (`_pos_sale_impl_body`).
- **Fix:** Block linking a second warehouse to a store when a warehouse is created or edited (warehouse create/update with `store_id`, return 400/409 with a clear message), **or** make `warehouse_for_store` return one deterministic default warehouse instead of raising. Already listed as a gotcha in `AGENTS.md` ("POS store↔warehouse uniqueness").
- **Check:** Link two warehouses to one store (or try to and get a clear error), then complete a cash sale and a split sale at that store.

### [x] 1.2 MEDIUM: dashboard leaves out expenses that have no store
- **Problem:** The owner's dashboard is store-scoped, so approved expenses with `store_id = NULL` are not counted. Demo company: dashboard Expenses GH₵ 0.00 vs Reports GH₵ 140.00. Net position and Gross profit are overstated.
- **Where:** `backend/app/dashboard.py` ~line 150: `expenses_stmt = apply_store_scope(expenses_stmt, m.Expense.store_id, store_id, store_ids)`.
- **Fix:** For owners / company admins include company-wide expenses (`store_id IS NULL`) alongside the store's own, or label the card "This store only". Keep Reports and Dashboard consistent.
- **Check:** Approve an expense with no store; the dashboard Expenses card matches the Reports figure.

### [x] 1.3 MEDIUM (design): owner-console page titles unreadable
- **Problem:** On every `/platform/*` page the title (Billing, Tenants, Reports…) is near-black on the dark green banner.
- **Where:** `frontend/app/globals.css`: `.main h1:not(.greet){color:var(--ink)}` (~line 309) has higher specificity than `.plat-hero h1{color:var(--sand)}` (line 684).
- **Fix:** Add `.main .plat-hero h1{color:var(--sand)}` (and keep the dark-theme rule in step).
- **Check:** `/platform`, `/platform/billing`, `/platform/tenants` show a light title on green.

### [x] 1.4 LOW (design): Sales header steps run together on desktop
- **Problem:** Header reads "1 Customers2 Quotes3 Orders4 Invoices5 Returns".
- **Where:** `frontend/app/(dashboard)/sales/sales-ui.css`: `.sales-ui-path` only gets `display:flex; gap` inside the phone media query (~line 145).
- **Fix:** Move `display:flex; flex-wrap:wrap; gap:4px 10px;` into the base `.sales-ui-path` rule (line 8).
- **Check:** `/sales` at desktop width shows the five steps spaced apart.

### [x] 1.5 LOW (design, phone): sidebar arrow covers page text
- **Problem:** At ~390 px wide the green "›" sidebar toggle on the left edge overlaps content (greeting name, page intros, "Supplier balances").
- **Where:** Dashboard shell sidebar toggle styles (`frontend/app/(dashboard)` layout / shell CSS in `globals.css`).
- **Fix:** Add left padding to the main content at phone width, or move the toggle into the top bar.
- **Check:** Dashboard, Inventory and Purchasing at 390 px: no text covered.

### [x] 1.6 LOW: Credit page asks for the wrong record after switching to Payables
- **Problem:** Receivables → Payables requests the previously selected customer as a supplier: `GET /api/v1/suppliers/{customer-id}/credit` → 404 (console only).
- **Where:** `frontend/app/(dashboard)/credit/page.tsx` ~line 330 `loadCreditInfo()` uses the stale `partyId`.
- **Fix:** Clear `partyId` and credit info when `kind` changes, before loading.
- **Check:** Credit: Receivables, then Payables — no 404 in the console.

### [x] 1.7 LOW: retail Batches tab calls a pharmacy endpoint
- **Problem:** Inventory › Batches calls `/api/v1/pharmacy/batch-holds` → 403 for retail companies (console error).
- **Where:** `frontend/app/(dashboard)/inventory/page.tsx:697` and `:1900`.
- **Fix:** Only call it when the pharmacy module is enabled for the tenant.
- **Check:** Retail company, Inventory › Batches — no 403 in the console.

### [x] 1.8 LOW: a shop cannot close its own support ticket
- **Problem:** Shop presses Close after a reply → 409 `INVALID_STATUS_TRANSITION` "Only a resolved ticket can be closed". The owner must resolve it first.
- **Where:** Support close rule behind `POST /api/v1/support/tickets/{id}/close`, and the shop's Close button on `/support`.
- **Fix:** Decide the rule: allow shops to close open tickets, **or** hide the shop's Close button until the ticket is resolved.
- **Check:** As a shop: open a ticket, get an owner reply, close it (or see no Close button).

---

## 2. Commit and deploy fixes already in the working copy

The production folder is on a **detached HEAD with ~88 changed files**. These fixes exist but are not committed.

### [ ] 2.1 Commit the database-column mapping fix
- **Problem (fixed locally):** Add supplier, add customer, create sales invoice, custom roles, recurring expenses, PO amend and AI query logging failed with `NotNullViolationError` because the DB had NOT NULL columns the models did not map (`parties.created_at/updated_at`, `sales_invoices.credit_limit_overridden`, `stock_reservations.updated_at`, `purchase_order_amendments.revision`, `recurring_expenses.skip_next`, `custom_roles.slug`, `ai_queries.message/answer`). `backend/app/models.py` and `backend/app/sales.py` now map them; a schema check finds no remaining unmapped NOT NULL columns.
- **Fix:** Commit on `main`, run tests, merge to `production`.
- **Check:** After deploy: add a supplier, add a customer, create and post a sales invoice.

### [ ] 2.2 Check the live database for the same column problem
- **Fix:** On the live Postgres run:
  ```sql
  SELECT table_name, column_name FROM information_schema.columns
  WHERE table_schema='public' AND is_nullable='NO' AND column_default IS NULL
    AND table_name IN ('parties','sales_invoices','stock_reservations','purchase_order_amendments',
                       'recurring_expenses','custom_roles','ai_queries');
  ```
- **Check:** Every column returned is mapped in the deployed `models.py`.

### [ ] 2.3 Run migrations on the live server
- **Fix:** `alembic upgrade head` in the backend container after deploying.
- **Check:** `alembic current` shows `20261022_0142 (head)` (same as local).

---

## 3. Repair the test suite

Full run: **2,979 passed, 55 failed** (run with the whole repo mounted). None of the failures is a broken retail feature.

### [x] 3.1 Fix the test file that cannot load
- **Problem:** `backend/tests/test_pos_offline_journal_r1.py` → `ModuleNotFoundError: No module named 'journal'`; stops collection of the whole suite.
- **Fix:** Correct the import (module lives under `app/`).
- **Check:** `pytest --co -q` collects with no errors.

### [x] 3.2 Update ~42 screen-text tests after the UI redesign
- **Problem:** Tests assert old labels, e.g. `aria-label={`Cancel sales invoice ${inv.id}`}`. Cancel/reject with a reason still exist; they moved into row menus (e.g. `transferAct(t.id, 'reject')` in `inventory/page.tsx`).
- **Files:** `backend/tests/test_*_cancel_reason_*`, `test_*_reject_reason_*`, `test_*_ui_and_docs`, `test_po_amend_reason_*`, `test_sales_discount_ui.py`, `test_inventory_low_stock.py`, `test_pos_payment_reference_openapi_r1.py`, `test_pos_session_close_notes_openapi_r1.py`, `test_pos_shift_status_openapi_r1.py`, `test_pos_till_checkout_ui_r1.py`, `test_purchasing_company_admin_ux.py`, `test_soft_activate_btn_colors_r1.py`, `test_credit_override_*`, `test_document_email_to_openapi_r1.py`, `test_honesty_defense_batch12_openapi_r1.py`, `test_webauthn_base64url_fe_omit_openapi_r1.py`, `test_opening_stock_line_product_id_openapi_r1.py`, `test_stock_*_openapi_r1.py`, `test_pr_convert_supplier_id_openapi_r1.py`, `test_purchase_request_item_notes_openapi_r1.py`.
- **Fix:** Point assertions at the current labels/helpers.
- **Check:** These tests pass.

### [x] 3.3 Update three tests with outdated expectations
- `test_alembic_revision_graph.py:74` expects head `20261011_0138`; now `20261022_0142`.
- `test_expense_category_coa_c1.py:39` → "Account code already exists"; use a code not in the default chart of accounts.
- `test_honesty_defense_batch26_openapi_r1.py:151` expects `return money_json(on_hand - reserved)`; match current `available_qty`.
- **Check:** All three pass.

### [x] 3.4 Mark server-only tests
- **Problem:** Fail on a laptop because they need `/opt/ribdigi` or a throwaway DB: `test_ops_monitoring_m1`, `test_k8s_deploy_k1`, `test_load_capacity_c1`, `test_load_cert_pack_c1`, `test_pitr_drill_pack_r1`, `test_wal_pitr_w1`, `test_grafana_pack_a1`, `test_logical_dr_drill_b1`, `test_celery_reliability_r1`, `test_dokploy_source_revision`, `test_alembic_disposable_upgrade`.
- **Fix:** `pytest.skip` when the path/DB is unavailable, or run them only in CI.
- **Check:** A local run has no environment-only failures.

(Out of scope: `test_tenants.py::test_normalize_industry_accepts_and_rejects` expects pharmacy to be rejected.)

---

## 4. Before charging customers (setup, not code bugs)

### [ ] 4.1 HIGH: set up outgoing email
- `SMTP_HOST` is empty → no email verification, password reset, invoice/PO/report emails, or support-desk emails (desk already counts "Failed email").
- **Check:** New user gets the verification email; password reset works.

### [ ] 4.2 HIGH: decide how shops pay for subscriptions
- Paystack and Flutterwave are supported (`backend/app/billing_gateway.py`), but the owner console says paid self-serve checkout is not live.
- **Fix:** Add live gateway keys and test one real payment, or invoice shops manually.

### [ ] 4.3 HIGH: Terms of Service and Privacy Policy
- No terms/privacy pages for the ERP itself (only storefront policies). Add both and link them from login and sign-up.

### [ ] 4.4 MEDIUM: confirm production security settings
- Strong `JWT_SECRET_KEY` (production already rejects weak ones), `LOGIN_2FA_ENABLED=true`, `PUBLIC_APP_URL`, error monitoring (`SENTRY_DSN` empty).

### [ ] 4.5 LOW: AI chat
- Answers 503 "not configured". Configure an approved provider (`AI_ENABLED`, `AI_PROVIDER`) or hide AI chat from paying shops. Rule-based insights already work.

### [ ] 4.6 LOW: SMS
- Twilio not configured → no SMS receipts/alerts. Configure it or don't advertise SMS.

### [x] 4.7 LOW: till offline helper
- Every till load tries `http://127.0.0.1:8765` (`frontend/lib/posOfflineJournal.ts:9`) and logs a connection error. Ship the helper or skip the call when it isn't installed.

---

## What already works (verified end to end)

Company setup, branches, departments, warehouses, staff and custom roles · categories, brands, units, tax rates, products, barcode generate/label · stock in/out/adjust, transfers (approve/ship/receive), stock counts, low stock · suppliers, purchase requests, POs (amend, email), GRN, purchase invoices, supplier payments, purchase returns · customers, quotation → order (reserves stock) → invoice, invoice post/print, customer payments, sales returns · POS shift open/close, cash and credit sales, receipt, shift report · expenses, recurring expenses, bank account, cash transfer, manual journal · all main reports with CSV/Excel/PDF export · backup, API keys, webhooks, audit log, notifications · Help & Support round trip (shop ticket → owner desk → reply; internal notes hidden from the shop) · owner console (tenants, subscriptions, usage, billing, reports, staff, jobs). No blank pages, crashes, NaN/undefined text, or sideways scrolling on phones. Frontend `tsc --noEmit` passes.

## Local test accounts (delete when done)

| Account | Sign in | Password |
|---|---|---|
| Shop "Audit Check Shop" | company `audit-check`, `owner@auditcheck.example.com` | `AuditCheck-2026-Local!` |
| Owner console | company `platform`, `owner-audit@platform.example.com` | `OwnerAudit-2026-Local!` |
