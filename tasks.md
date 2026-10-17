# Task tracker

IDs are stable. Status values: Not started, In progress, Blocked, Implemented awaiting verification, Done.

Evidence is a command outcome or a file inspection. Prior results cited from `docs/COMMERCIAL_READINESS_REPORT.md` or `docs/RETAIL_FEATURE_MATRIX.md` were not re-run for this file. Do not treat a loaded screen as a finished module.

## 17 October 2026 UTC

| ID | Priority | Finding | Required fix | Status | Acceptance criteria | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| T-OWN-17 | P0 | Software owner could not hard-delete a company with org FK cycles; directory hid create-account email; admin reset was link-only | Clear cyclic manager/branch/dept FKs before purge; expose `admin_email` on platform directory; allow `new_password` on admin-password-reset (never echo) | Done | Owner deletes a tenant with branch manager + store manager + product. Directory shows admin email. Set password logs in; bare `password` stays 422 | From `backend`, `PYTHONPATH=.`, `RATE_LIMIT_BACKEND=memory`, Python 3.12: `pytest tests/test_platform_tenant_delete_r1.py tests/test_platform_owner_console_r1.py -q --tb=line`. **17 passed** in 77.16s. In-memory SQLite. `ribdigi_erp` was not opened |
| T-OWN-17b | P0 | Live Postgres still returned 409 on tenant delete; SQLite tests had FK checks off | Null all nullable tenant FKs; multipass delete with savepoints; FK-on purge test with journal lines | Done | Delete succeeds with branch/store managers, product, and posted journal under `PRAGMA foreign_keys=ON` | From `backend`, `PYTHONPATH=.`, `RATE_LIMIT_BACKEND=memory`, Python 3.12: `pytest tests/test_platform_tenant_purge_postgres_shape_r1.py tests/test_platform_tenant_delete_r1.py::test_owner_can_delete_tenant_with_org_records tests/test_platform_tenant_delete_r1.py::test_delete_leaves_the_other_tenant -q --tb=short`. **3 passed** in 29.31s |
| T-OWN-17c | P1 | Admin email easy to miss in tenant manage detail (muted h2 only; usage omit) | `admin_email` on `/tenants/{ref}/usage`; clear Administrator email in manage panel + managing banner | Done | Manage panel shows create-account admin email; usage JSON includes `admin_email` | From `backend`, `PYTHONPATH=.`, `RATE_LIMIT_BACKEND=memory`, Python 3.12: `pytest tests/test_platform_owner_console_r1.py::test_platform_directory_and_activity_skip_store_ops -q --tb=line` |
| T-OWN-17d | P0 | Purge still incomplete for live Postgres (ORM-only table walk; opaque 409) | Reflect live `tenant_id` tables + nullable FKs; multipass delete; recount leftovers in 409 | Done | FK-on SQLite purge with journal + expense + customer + org cycles; leftover table names in 409 when stuck | From `backend`, `PYTHONPATH=.`, `RATE_LIMIT_BACKEND=memory`, Python 3.12: `pytest tests/test_platform_tenant_purge_postgres_shape_r1.py tests/test_platform_tenant_delete_r1.py::test_owner_can_delete_tenant_with_org_records tests/test_platform_tenant_delete_r1.py::test_delete_leaves_the_other_tenant tests/test_platform_owner_console_r1.py::test_platform_directory_and_activity_skip_store_ops -q --tb=short`. **4 passed** in 36.66s |

## 15 October 2026 UTC

| ID | Priority | Finding | Required fix | Status | Acceptance criteria | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| T-RBAC-15 | P0 | A cashier with till `credit:write` could record a supplier payment | Require `credit:read` on `POST /suppliers/{id}/payments`. Do not narrow customer or POS credit | Done | Cashier post is 403. A company admin is not refused by that check | From `backend`, `PYTHONPATH=.`, `RATE_LIMIT_BACKEND=memory`, Python 3.12: `pytest tests/test_cashier_pos_only.py -q --tb=short`. **4 passed** in 6.44s. Cashier 403. Company admin on a missing supplier 404. In-memory SQLite. `ribdigi_erp` was not opened |
| T-BAK-15 | P1 | Local isolated restore of `ribdigi_erp` | Dump only after `current_database()` is `ribdigi_erp`. Restore into a new database that is not `ribdigi_erp`, `production`, or `staging`. Drop it | Done for this local copy | User, sale or journal counts match. A second tenant is not mixed. The disposable database is gone | PostgreSQL 16.14 `pg_dump` / `pg_restore` inside `ribdigi-erp-postgres-1`. Disposable `ribdigi_drill_20261015`: users 9, tenants 6, sales 40, journals 50, tenant-mix checks 0. Dropped, and the dump file removed. `current_database()` on `ribdigi_erp` still `ribdigi_erp`. Not a `.ribbak` or production restore |
| T-OFF-15 | P1 | Queue replay after the browser database closes | Automated prepare, sell, close IndexedDB, flush the same `client_request_id` once | Done. Offline POS is Ready. Not Offline Complete | One API call and one synced row. `offline_complete_claimed` stays false | `frontend` `npm run test:offline`: **21 passed**, 0 failed, exit 0. Includes “offline complete stays missing”. Does not prove a closed browser uploads, private-window recovery without the till-agent journal, or strong device binding |
| T-WALK-15 | P1 | Signed-in retail receipt through report | Do not sign the drill cashier in | Done for the disposable test company | One retail sale reconciled receipt, sale, stock, tender, journal, and report on a test company | From `backend`, `PYTHONPATH=.`, `RATE_LIMIT_BACKEND=memory`, Python 3.12: `pytest tests/test_retail_pos_arithmetic_fixture.py -q --tb=short`. **1 passed** in 6.25s, exit 0. Receipt total 220, stock 18, cash on 1000, one balanced journal, replay of the same sale, daily `pos_revenue` and `total_revenue` 220. In-memory SQLite. `ribdigi_erp` was not opened. Unsigned `/pos` returned to the login form. Multi-store, hotel, and restaurant were not walked |
| T-SEC-15 | P0 | Security ready only when the local checks have run; Verified still needs the remaining checks | Do not mark Security Verified from the local restore or the in-memory suite alone | Ready | Signed-in browser, live site, full backend suite, and external test are still required before Verified | From `backend`, `PYTHONPATH=.`, `RATE_LIMIT_BACKEND=memory`, Python 3.12: the named auth, isolation, 2FA, upload, billing, and cashier-presence files. **123 passed** in 285.97s, exit 0. In-memory SQLite. `ribdigi_erp` was not opened. Unsigned `/security` and `/pos` on `http://127.0.0.1:3000` returned to the login form. Not Verified. Not certified. Live health was not requested |
| T-ISO-15 | P0 | A signed billing webhook could treat a missing company, amount, or currency as a match. A store manager could list cashiers from stores they are not assigned to | Require company, amount, and currency on the webhook. Limit cashier presence to `assigned_store_ids` when memberships exist | Done | An open invoice stays open when those fields are omitted. A matching webhook still saves the method. A manager assigned to one store does not see the other store's cashier. A company admin still sees both. A manager with no membership still sees the company cashiers | From `backend`, `PYTHONPATH=.`, `RATE_LIMIT_BACKEND=memory`, Python 3.12: `pytest tests/test_saas_billing_r1.py tests/test_cashier_presence.py tests/test_billing_gateways.py -q --tb=line`. **23 passed** in 65.58s. In-memory SQLite. `ribdigi_erp` was not opened. Included again in the 123-test security command |
| T-ISO-16 | P0 | A store manager with `users:read` could list and open staff assigned only to another store, including by `?store_id=` | Limit `GET /users` and user-by-id routes to the viewer's stores. Another store id returns 403. No membership still means the whole company | Done | Manager assigned to store A sees roster A and not roster B. Direct get of roster B is 404. `?store_id=` for store B is 403. Company admin still sees both | Same security command, `tests/test_user_store_membership_rbac.py::test_store_manager_user_list_stays_inside_assigned_stores` inside **123 passed** |

## 2026-10-14 review rows

| ID | Priority | Finding | Required fix | Status | Acceptance criteria | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| T-POS-03 | P0 | A gift-card or loyalty tender that also sent a cash account id could debit till cash 1000 | Ignore that account id for gift card and loyalty. Reject any other non-cash tender that resolves to 1000. Refunds of those tenders credit 2150 or 2160 | Done | Gift-card journal debits 2150. Mobile Money with a cash account id returns HTTP 400. A refund does not credit 1000 | Earlier isolated run: 6 passed in 15.87s. Later the file has 10 tests, including inactive bank 1010, inactive loyalty 2160, and a drawer total that keeps only cash. They passed inside the 2026-10-14 evening combined run (the only failure was the login-copy assertion, later repaired). In-memory SQLite. `ribdigi_erp` was not written. `api.py` replay was not edited |
| T-ADM-14 | P0 | Removing the only active company admin | Keep the existing refusal | Done | Deactivate and reassign of the last company admin fail | `tests/test_users_roles.py::test_last_company_admin_cannot_be_deactivated_or_reassigned` passed in the 2-test run (6.01s) |
| T-DASH-14 | P1 | Dashboard purchases must not add drafts or purchase orders on top of bills | Keep recorded supplier bills plus leftover legacy purchase transactions | Done | Unpaid, partial, paid, and overdue count. Drafts stay out | `tests/test_dashboard.py::test_dashboard_purchases_count_recorded_bills_not_drafts` passed in that same run. Not re-run in the later pass |
| T-REC-14 | P1 | One posted sale must match stock, tender, and journal | Read-only check on the local database only. Replay a lost response in the test database | Done for sale POS20260036 and for the in-memory replay | One sale, one tender, one stock movement, one balanced journal | Earlier read-only `ribdigi_erp` on 127.0.0.1 after `current_database()`: total 5.75, cash tender 5.75, stock-out 1, posted journal debit 7.75 credit 7.75. 0 duplicate groups. 0 unbalanced journals. Protected shifts were not updated. Later, `tests/test_pos_sale_replay_r1.py` plus the existing idempotent and quote tests: 7 passed in 32.03s. That live sale was not read again |
| T-BAK-14 | P1 | Isolated restore was not repeated | Do not restore over `ribdigi_erp`. Use an authorized backup file only | Blocked | An authorized backup is restored into a new disposable database, then that database is dropped | 2026-10-14 evening: `docker exec ribdigi-erp-postgres-1` shows `psql`, `pg_dump`, and `pg_restore` PostgreSQL 16.14. Backend `/data/backups` is volume `ribdigi-erp_backup_data` and `ls -la` shows only `.` and `..`. No `.ribbak`, `.dump`, or `.backup` in this tree. No disposable database was created. `ribdigi_erp` was not dumped |
| T-WALK-14 | P1 | Signed-in retail, hotel, and restaurant screens | Use an existing local session. Do not print a password | Not run | Click retail single-store, retail multi-store, hotel, and restaurant while signed in, each judged on its own | 2026-10-14 evening: `GET http://127.0.0.1:3000/` returned 200. The HTML contains Login tenant, Login email, Login password, and Sign in. The drill cashier was not signed in. No password script was written |
| T-LIVE-14 | P1 | Live site health | Do not retry the previously blocked check | Not run | Do not infer live health from local tests | `https://erp.ribdigihouse.com/api/v1/health` was not requested |
| T-OFF-14 | P1 | Offline Complete must stay unclaimed | Leave `offline_complete_claimed` false | Done as a non-change | The flag stays false. The journal file keeps the original `client_request_id` | `backend/app/offline_pos.py` still returns `offline_complete_claimed` false. 2026-10-14 evening: `frontend` `npm run test:offline` **20 passed**, 0 failed, exit 0. That does not prove a closed browser uploads, a private window recovers a sale, or strong device binding |
| T-SEC-14 | P0 | Full access, isolation, 2FA, rate-limit, XSS, and SSRF suite | Do not invent a new auth system | Blocked | Those tests pass, and the remaining checks are executed, before security is called verified | Earlier same day: auth, 2FA, WebAuthn, tenant isolation, permissions, offline isolation, rate limit, OWASP, expense attachments, product images, and brand logo: 99 passed in 210.51s. Evening command of the suites not in that list (password reset, email verify, stale login header, TOTP, users/roles, custom roles, cashier limits, backup isolation, storage, product and user import, expense and purchase OCR, company logo, attachment preview, hotel cross-tenant): first **1 failed, 99 passed** in 201.44s. The failure was login copy. After the repair, `tests/test_login_stale_session_header_l1.py`: **3 passed** in 6.36s. The full backend suite, a signed-in walkthrough, the live site, and an authorized restore were not executed |
| T-DUP-14 | P0 | A lost sale response could be posted twice, or a reused id could change the sale | Replay the same `client_request_id`. Reject a different body | Done for the in-memory fixture | Exactly one sale, one tender set, one stock effect, and one journal. A different quantity is HTTP 409 | `tests/test_pos_sale_replay_r1.py`, `tests/test_pos_sale_client_request_id_idempotent.py`, and `tests/test_offline_pos_grants.py::test_offline_quote_capture_is_idempotent`: 7 passed in 32.03s. Two overlapping inserts were not proven on the one SQLite connection. The missed-lookup race returned the original sale |

## Auth and isolation

### T-AUTH-01 — Tenant isolation on reads and writes

- Priority: P0
- Requirement: Operational queries use the authenticated `tenant_id`. A mismatched `X-Tenant-ID` is rejected.
- Module: `backend/app` auth and tenant filters; `docs/ADR_001_TENANCY.md`
- Dependencies: none
- Status: Implemented awaiting verification
- Acceptance: Cross-tenant access tests pass on a disposable database.
- Evidence: Report records `tests/test_tenant_isolation_matrix.py` and `tests/test_offline_pos_isolation.py` inside a 57-test slice (178.39s). Not re-run here.
- Blocker: none

## Roles and plan access

### T-RBAC-01 — Server-side role checks

- Priority: P1
- Requirement: Cashier, sales officer, inventory officer, accountant, store manager, and company admin are enforced on the API. The last active company admin cannot be removed.
- Module: RBAC dependencies, users
- Dependencies: T-AUTH-01
- Status: Implemented awaiting verification
- Acceptance: Last-admin deactivate, reassign, and delete are refused until a second company admin exists.
- Evidence: Report records 6 passed in 20.67s. 2026-10-14 re-ran only `test_last_company_admin_cannot_be_deactivated_or_reassigned`: passed inside a 2-test run (6.01s).
- Blocker: Full role matrix was not re-executed.

### T-USER-01 — Company admin can add a person and finish follow-ups

- Priority: P1
- Requirement: On User management, a company administrator can add a person, see the list, and complete role, branch, department, record scope, activate, deactivate, custom role, and CSV follow-ups. Cashier presence stays on this page.
- Module: `frontend/app/(dashboard)/users/page.tsx`, `frontend/app/globals.css` user-manage rules
- Dependencies: T-RBAC-01
- Status: Implemented awaiting verification
- Acceptance: Create trims name and password, sends phone as E.164 or null, and sends the role key. Custom-role saves stay on read, write, approve, or a module-wide grant. CSV template and import do not send a non-UUID tenant header. Empty states say what to do next. A signed-in User management screen is clicked through.
- Evidence: From `backend`, `PYTHONPATH=.` and Python 3.12 `pytest` of the user, role, CSV, and users-page source tests: **115 passed** in 195.34s (2026-10-14). `npx tsc --noEmit --pretty false --incremental false` from `frontend` exited 0. The open browser at `http://127.0.0.1:3000/users` redirected to the login form. No password was entered. The signed-in User management screen was not opened.
- Blocker: Signed-in click-through still needs an existing admin session. Do not type the drill password.

### T-PLAN-01 — Package module gates

- Priority: P1
- Requirement: Trial, starter, professional, and enterprise gate modules. Sidebar hiding is not the only control.
- Module: `packages`, tenant modules
- Dependencies: T-AUTH-01
- Status: Implemented awaiting verification
- Acceptance: Disabled modules fail on the API for that tenant.
- Evidence: Code inspection of package entitlements. Entitlement fixture not re-run. Prices were not changed.
- Blocker: none

## Stores and warehouses

### T-STORE-01 — Active store cap

- Priority: P1
- Requirement: Empty cap means unlimited. Negative caps are rejected. Downgrade does not delete stores. Create and activate count active stores.
- Module: `backend/app/store_entitlements.py`
- Dependencies: T-PLAN-01
- Status: Implemented awaiting verification
- Acceptance: Over-cap create and activate return a store-limit error. Existing stores remain.
- Evidence: Report records `tests/test_subscription_store_limits_r1.py` inside the 57-test slice. Service file confirms active count and no delete on downgrade.
- Blocker: Browser confirmation not run.

### T-WH-01 — One warehouse link per store

- Priority: P0
- Requirement: POS must not 500 when a store has two warehouses with the same `store_id`.
- Module: stores, POS sale
- Dependencies: T-STORE-01
- Status: Implemented awaiting verification
- Acceptance: Duplicate `store_id` on warehouses is rejected or the extra link is not created. A sale against a single-link store posts.
- Evidence: `AGENTS.md` records the `MultipleResultsFound` failure mode. No new test run here.
- Blocker: none

## POS, receipts, and shifts

### T-POS-01 — Shift, receipt, and recorded tenders

- Priority: P1
- Requirement: Open shift with opening cash, reuse an open shift, print a receipt, and record cash, card, Mobile Money, and bank transfer without capturing funds. Mobile Money posts to GL 1010.
- Module: POS, accounting
- Dependencies: T-AUTH-01, T-STORE-01
- Status: Implemented awaiting verification
- Acceptance: One completed sale has one tender, one balanced journal, and shift totals that include that sale only.
- Evidence: `backend/app/accounting.py` maps `mobile_money` to 1010. Report records one local cash sale on `offline-drill-oct13` (stock 8 to 7, journal balanced, shift `SHIFT-2026-0001` left open). Do not close that shift. 2026-10-14 checkout pass: Charge sends the cart on screen (`session_id` trimmed when a shift is open, `party_id` trim or null, `customer_name` from the name field trim or null, blank tender `reference` null, credit `override_reason` only after an over-limit confirm). A split mismatch no longer reposts rescaled amounts. A changed cart gets a new `client_request_id`; a confirmed sale clears it. Card, Mobile Money, and bank transfer stay recorded tenders. Wallet, gift card, and loyalty stay online-only. From `backend`, `PYTHONPATH=.` and Python 3.12 `pytest` of the POS checkout, payment-reference, session, party, customer-name, and scan-print source tests: **18 passed** in 18.91s. Those tests use in-memory fixtures or source reads. `ribdigi_erp` was not opened. `SHIFT-2026-0001`, `SHIFT-2026-0002`, and `SHIFT-2026-0007` were not closed.
- Blocker: Signed-in till not used in this pass.

### T-POS-03 — Stored-value tenders must not debit till cash

- Priority: P0
- Requirement: Gift card and loyalty debit 2150 and 2160 even if a cash account id is sent. Mobile Money, card, and bank transfer that resolve to till cash 1000 are rejected.
- Module: `backend/app/accounting.py`, `backend/app/pos.py`
- Dependencies: T-POS-01
- Status: Done
- Acceptance: The new routing test passes. Issuing a gift card still debits 6100 because that screen does not collect cash.
- Evidence: `tests/test_payment_gl_routing.py`: **6 passed** in 15.87s (2026-10-14). In-memory SQLite. `ribdigi_erp` was not opened.
- Blocker: none for this posting rule. A signed-in redemption was not clicked.

### T-POS-02 — Counted cash close

- Priority: P1
- Requirement: An authorized count records actual cash and variance. Pending offline sales for that shift block the count. Sign-out still uses expected cash when the queue is readable.
- Module: POS shifts
- Dependencies: T-POS-01, T-OFF-03
- Status: Implemented awaiting verification
- Acceptance: Tests cover variance and the sign-out path. Browser click is separate.
- Evidence: Report records `tests/test_pos_cash_movements.py` 3 passed in 8.20s. Not re-run here.
- Blocker: none

## Offline

### T-OFF-01 — Prepare and expiring grant

- Priority: P1
- Requirement: Unprepared and expired devices show the exact sentences in `rule.md`. Grant is device + company + user. No plaintext password. New offline sales stop after expiry. Queued sales remain.
- Module: `frontend/lib/connectivity.ts`, `backend/app/offline_pos.py`
- Dependencies: T-AUTH-01
- Status: Implemented awaiting verification
- Acceptance: Copy matches `UNPREPARED_OFFLINE` and `EXPIRED_OFFLINE`. `offline_complete_claimed` stays false. A signed-in online till prepares without a Refresh click. The unprepared sentence stays only when there is still no grant.
- Evidence: File inspection of those constants and `policy_payload`. `frontend` `npm run test:offline` on 2026-10-14: **20 passed**, 0 failed, including “offline complete stays missing”, the unprepared/expired sign-in sentences, and “signed-in online till does not keep the unprepared sentence after prepare”. A signed-in Point of Sale screen was not opened. The local sign-in page at `http://127.0.0.1:3000/` was the login form; nobody was signed in. After a reload with `GET /api/v1/health` returning 200, that page did not show the unprepared sentence. `offline_complete_claimed` stays false.
- Blocker: No signed-in Point of Sale check in this pass.

### T-OFF-02 — Queue durability limits

- Priority: P0
- Requirement: Queue lives in encrypted IndexedDB. A closed browser cannot upload. Device id is not strong binding. The till-agent journal on this PC can restore a queued sale after site data is cleared, with the same client_request_id. A private window with no journal cannot. Offline Complete still needs strong device binding and a live site.
- Module: `frontend/lib/posOffline.ts`, `frontend/lib/posOfflineJournal.ts`, `ops/print-agent/journal.py`, `docs/OFFLINE_POS.md`
- Dependencies: T-OFF-01
- Status: Blocked
- Acceptance: Offline Complete only if binding, recovery, and a live site are all true. Recovery here is the on-PC journal only.
- Evidence: `docs/OFFLINE_POS.md` still says Offline Complete remains **MISSING**. `frontend` `npm run test:offline` on 2026-10-14: **19 passed**, 0 failed, including “queued sale is read back from the till journal after IndexedDB is cleared” (same `client_request_id` after the browser queue database was deleted). `npx tsc --noEmit --pretty false --incremental false` exited 0. `backend` `pytest tests/test_pos_offline_journal_r1.py -q --noconftest`: **4 passed** in 0.86s. That pytest did not open the app database. `offline_complete_claimed` stays false.
- Blocker: Browser device id is still not strong device binding. A private window with no till-agent journal cannot recover sales. No live site test. `offline_complete_claimed` stays false.

### T-OFF-03 — Automatic sync and manager conflicts

- Priority: P1
- Requirement: With the till open, sales upload without a Send button. 5xx, 429, 408, and network stay pending. Price, stock, and credit conflicts stay for a manager. Idempotency is `(tenant_id, client_request_id)`. Sync does not silently change totals.
- Module: `frontend/lib/posOffline.ts`, POS sale API
- Dependencies: T-OFF-01, T-POS-01
- Status: Implemented awaiting verification
- Acceptance: Replay returns the original sale. A conflict row is not posted.
- Evidence: Flush loop inspected (`flushOfflineQueue`). Report records same-tenant replay and the 2026-10-13 local sync. Not re-run here.
- Blocker: Live site not tested.

## Inventory, sales, purchasing, ledger

### T-INV-01 — Inventory and transfers

- Priority: P1
- Requirement: Stock moves stay tenant-scoped. Single-store must not transfer. Multi-store transfer requires both ends.
- Module: inventory, stores
- Dependencies: T-STORE-01
- Status: Implemented awaiting verification
- Acceptance: Single-store transfer is forbidden. Multi-store transfer posts when stock exists.
- Evidence: Matrix records prior API results. Not re-run here. Browser pass not run.
- Blocker: none

### T-SALES-01 — Invoices, returns, and credit

- Priority: P1
- Requirement: Posted invoices, returns, and credit limits stay on the server. An over-limit offline sale waits for a manager.
- Module: sales, credit, POS
- Dependencies: T-AUTH-01, T-OFF-03
- Status: Implemented awaiting verification
- Acceptance: Arithmetic fixture and sales document tests pass. Credit conflict is not auto-posted.
- Evidence: Report records arithmetic fixture 1 passed and sales/cashier/stores 12 passed. Not re-run here.
- Blocker: Full quote, order, and return browser pass not run.

### T-PUR-01 — Purchasing and expenses

- Priority: P1
- Requirement: Purchasing and expenses stay online-only and tenant-scoped.
- Module: purchasing, expenses
- Dependencies: T-AUTH-01
- Status: Implemented awaiting verification
- Acceptance: Offline policy lists them under not-offline. API tests for those modules pass when touched.
- Evidence: `docs/OFFLINE_POS.md` not-offline list. No new purchasing run here.
- Blocker: none

### T-LED-01 — Ledger and reports

- Priority: P1
- Requirement: Posted journals balance. Reports stay online-only. JSON money is a number from `honesty.money_json`.
- Module: accounting, reports, `backend/app/honesty.py`
- Dependencies: T-POS-01, T-SALES-01
- Status: Implemented awaiting verification
- Acceptance: A sale fixture has one balanced journal. Report endpoints reject bad dates with 422.
- Evidence: `money_json` inspected. Report records the local sale journal (cash 11.50, revenue 10.00, tax 1.50, COGS 2.00, inventory 2.00). Not re-run here.
- Blocker: Headline dashboard figures were not compared to the ledger in this pass.

### T-RPT-01 — Tenant Reports screen

- Priority: P1
- Requirement: A company user can open one report, read its numbers, apply the filters on screen, and export CSV, Excel, and PDF with those same filters.
- Module: `frontend/app/(dashboard)/reports/page.tsx`, `backend/app/report_export.py`, `GET /reports/export`
- Dependencies: T-LED-01
- Status: Implemented awaiting verification
- Acceptance: Generate applies filters. Blank dates and blank optional ids are omitted. Export status and reason match the report on screen. Sales by store and by department honor the chosen store. `money_json` is unchanged. A signed-in open of `/reports` is still required before Done.
- Evidence: `pytest tests/test_report_export_screen_filters_r1.py tests/test_report_export_query_openapi_r1.py tests/test_report_export.py tests/test_transfer_report_status_openapi_r1.py tests/test_stock_count_status_openapi_r1.py tests/test_pending_po_status_openapi_r1.py tests/test_return_report_status_openapi_r1.py tests/test_return_report_reason_openapi_r1.py tests/test_inventory_valuation_method_openapi_r1.py tests/test_sales_report_uuid_query_openapi_r1.py tests/test_sales_by_store_department_date_query_openapi_r1.py tests/test_sales_by_store.py tests/test_honesty_defense_batch7_openapi_r1.py tests/test_honesty_defense_batch17_openapi_r1.py tests/test_reports_page_r1.py tests/test_department_report_filters_d1.py -q --tb=line` from `backend` with Python 3.12 and `PYTHONPATH=.`: **65 passed** in 80.23s (2026-10-14). In-memory SQLite only; `ribdigi_erp` was not opened. `npx tsc --noEmit --pretty false --incremental false` from `frontend` exited 0 (2026-10-14). `http://127.0.0.1:3000/reports` redirected to the login page. Nobody was signed in.
- Blocker: The signed-in Reports screen was not opened.

## Subscription billing

### T-BILL-01 — Recorded customer payments versus subscription collection

- Priority: P1
- Requirement: POS tenders do not collect card or Mobile Money. Subscription invoices stay unpaid until a signed webhook matches amount, currency, and tenant.
- Module: billing, POS payments
- Dependencies: T-AUTH-01
- Status: Implemented awaiting verification
- Acceptance: Checkout return does not mark paid. Webhook tests pass. No live charge.
- Evidence: `docs/SAAS_BILLING.md`. `pytest tests/test_saas_billing_r1.py tests/test_platform_billing_roster.py tests/test_billing_gateways.py -q` from `backend` with Python 3.12 and `PYTHONPATH=.`: **32 passed** in 120.97s (2026-10-14). That run includes checkout return staying unpaid and signed-webhook matching. No live processor was called. In-memory SQLite only; `ribdigi_erp` was not opened.
- Blocker: No live gateway is configured. Do not add secrets. Paid billing is not Complete.

### T-BILL-02 — Company admin subscription screen

- Priority: P1
- Requirement: `/company/billing` shows this company's assigned plan, amount, term, Trial/Active/Grace/Suspended, trial end, next renewal, paid through, automatic renewal, payment method, renewal agreement, and this company's invoices. A return from the payment page does not mark an invoice paid.
- Module: `frontend/app/(dashboard)/company/billing`, `backend/app/billing_api.py`, `backend/app/saas_billing.py`
- Dependencies: T-BILL-01
- Status: Implemented awaiting verification
- Acceptance: An active company with no billing profile is not described as a trial and cannot consent. A paid renewal invoice description is the billed plan name. The honesty sentence stays exact. No pay-now control marks an invoice paid.
- Evidence: Same pytest command as T-BILL-01: **32 passed** (2026-10-14), including `test_active_company_without_billing_profile_shows_package_only` and the Professional monthly invoice description. `npx tsc --noEmit --pretty false --incremental false` from `frontend` exited 0 (2026-10-14). The open browser at `http://localhost:3000/` was the login page. The signed-in billing screen was not opened. The drill cashier was not signed in.
- Blocker: A signed-in click-through of `/company/billing` is still needed. Invoices stay unpaid until a signed webhook matches amount, currency, and tenant.

## Support and guides

### T-GUIDE-01 — Staff and customer guides

- Priority: P2
- Requirement: Authorized users can download the retail staff guide. Guide text matches the product (no Offline Complete claim, no pharmacy sidebar).
- Module: staff guide PDF builders, `docs/USER_MANUAL.md`
- Dependencies: none
- Status: Done
- Acceptance: PDF bytes start with `%PDF`. A retail guide does not say Offline Complete, certified, or pharmacy. Hotel and restaurant companies get their own steps. An FMCG module line is omitted when the company is a hotel.
- Evidence: `pytest tests/test_ops_repairs_round.py::test_staff_guide_follows_industry_and_role -q --tb=short` from `backend` with Python 3.12: **1 passed** in 0.87s (2026-10-14). The test builds the PDF and checks those sentences. The download route builds that PDF per company (`GET /staff-guide`). The signed-in download button was not clicked; both browser tabs were the login page. Later the same day, Help & Support (`/support`) lists what each topic covers and has **Open the guide** (`GET /staff-guide`). New-company copy says retail, hotel, or restaurant. That page does not say Offline Complete, certified, or pharmacy. `tests/test_staff_guide_permission_s1.py` and `test_staff_guide_follows_industry_and_role` were in a 19-passed run (26.82s). The signed-in guide button was not clicked; the browser was the login page.
- Blocker: none for the generated text. A click on Company → download still needs a signed-in session.

## UI

### T-UI-01 — Cashier presence placement

- Priority: P1
- Requirement: Cashier presence stays on User Management. It is not on the company dashboard.
- Module: `users/page.tsx`, `dashboard/page.tsx`. Do not edit `CashierPresencePanel.tsx` or cashier-board CSS in this task.
- Dependencies: none
- Status: Done
- Acceptance: Dashboard source has no `CashierPresencePanel` import. Users page still mounts it.
- Evidence: Read `frontend/app/(dashboard)/dashboard/page.tsx` (no import). `users/page.tsx` imports the panel and renders `<CashierPresencePanel />`.
- Blocker: none

### T-UI-02 — Company format follows the signed-in user

- Priority: P1
- Requirement: Every signed-in role, including cashier, receives company date, time, and number separators from `GET /me`. Saving Company profile updates open screens without requiring a manual reload. Cashiers do not need `GET /tenants/me`.
- Module: `backend/app/api.py` `/me`, `frontend/lib/useCompanyFormat.ts`, `frontend/lib/meCache.ts`, `frontend/lib/format.ts`, company profile save
- Dependencies: T-AUTH-01
- Status: Done
- Acceptance: `tests/test_formatting_f1.py` shows the cashier `/me` payload matches the patched tenant and `/tenants/me` is 403. Format cache invalidation notifies listeners. Company save calls that invalidation.
- Evidence: From `backend`, `PYTHONPATH=.` and Python 3.12 `pytest tests/test_formatting_f1.py -q --tb=line`: **3 passed** in 4.65s (2026-10-14). `frontend` `npm run test:offline` includes “company format cache reloads after invalidation” inside **18 passed**. Company save calls `invalidateMeCache()` (`frontend/app/(dashboard)/company/page.tsx`), which clears the format snapshot. Signed-in browser save was not clicked; the app was on the login page.
- Blocker: none

### T-UI-03 — Brand and accessibility

- Priority: P2
- Requirement: Brand `#4AB012` unchanged. Operated controls keep `aria-label`s. Personal light/dark theme remains `data-theme`.
- Module: `frontend/app/globals.css`, Shell
- Dependencies: none
- Status: Done
- Acceptance: `--brand` is `#4AB012`. Dark theme selector exists.
- Evidence: File inspection of `frontend/app/globals.css` lines 4 and 416.
- Blocker: none

### T-UI-04 — Retail wording a person can read

- Priority: P2
- Requirement: The company page must not tell someone to choose Pharmacy, Wholesale, FMCG, or Hospital. Dashboard figures say what they count, in full words. Drawer cash in and cash out name the amount and the reason.
- Module: company page, dashboard page, POS shift drawer, `backend/app/tenants.py` retired-industry message
- Dependencies: none
- Status: Done
- Acceptance: Invalid business-type copy names only Retail, Hotel, and Restaurant, and says this page cannot change it. Sales, purchases, expenses, net position, and gross profit hints match `build_dashboard`. Cash movement controls have specific `aria-label`s. Dashboard source still has no `CashierPresencePanel`.
- Evidence: File inspection after the edit. `npx tsc --noEmit --pretty false --incremental false` from `frontend` exited 0 (re-run after the sales, purchases, expenses, and gross-profit hints were aligned with `build_dashboard`). Browser tabs at `http://localhost:3000/` and `http://127.0.0.1:3000/` were the login form, so the dashboard and company screens were not clicked. No password was entered.
- Blocker: Signed-in click-through still needs an existing admin session. Do not type the drill password.

### T-UI-05 — Restaurant order words

- Priority: P2
- Requirement: Restaurant order choices read as words. The kitchen action says “Send to kitchen”. Stored values stay `dine_in`, `takeaway`, `delivery`, and the existing payment codes.
- Module: `frontend/app/(dashboard)/restaurant/page.tsx`
- Dependencies: none
- Status: Implemented awaiting verification
- Acceptance: Visible option text is Dine in, Takeaway, Delivery, Cash, Card, Wallet, Mobile Money, and Credit. The kitchen button text is “Send to kitchen”. `npx tsc` exits 0. A signed-in restaurant page shows those words.
- Evidence: File inspection. `npx tsc --noEmit --pretty false --incremental false` from `frontend` exited 0 after the edit. Both browser tabs were the login page, so `/restaurant` was not opened.
- Blocker: Signed-in browser check was not done.

### T-UI-06 — Printer choices next to the print action

- Priority: P2
- Requirement: Paper size sits next to the button that prints. 58mm, 80mm, and A4 say what will print. Browser print is the path. No claim that a physical printer was tested.
- Module: `frontend/app/(dashboard)/pos/page.tsx`, `frontend/app/(dashboard)/sales/page.tsx`, `frontend/app/(dashboard)/printers/page.tsx`, `frontend/components/PosPrintStatus.tsx`, `frontend/app/globals.css`
- Dependencies: none
- Status: Implemented awaiting verification
- Acceptance: POS receipt paper stays `aria-label="POS receipt paper"` and sits with Pay. Sales keeps `aria-label="Print sales invoice A4"` and `aria-label="Print sales invoice thermal"`. Provisional offline copy stays “Offline sale — pending synchronization.” `npx tsc` exits 0. A signed-in POS, Sales, and Printers screen shows the paper choice beside the print button and stacks on a narrow screen.
- Evidence: 2026-10-14 follow-up. The size next to Pay changes only the browser receipt. The helper under Receipt paper was removed: “This size changes only the browser receipt. Reprint of that browser receipt uses the same size. A paired till agent uses the paper size stored on that printer.” The control stays `aria-label="POS receipt paper"` with 58mm and 80mm. `tests/test_pos_till_scan_print_r1.py::test_pay_prints_receipt_once` now requires those sentences to be absent. A paired till agent and a network printer use the paper size stored on that printer; the sale message and Reprint still say so, and Reprint does not open a browser receipt for a queued till-agent job. Saving a till-agent printer requires a paired agent and does not send a blank host. Purchase-return print (`GET /purchasing/returns/{id}/print`) and barcode labels (`GET /products/{id}/barcode/label`, copies and symbology only) have no paper parameter and were left unchanged. The Printers page says sales invoice Print and barcode labels do not send a till-agent job. From `backend`, `PYTHONPATH=.` and `C:\Users\arthu\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/test_pos_till_scan_print_r1.py tests/test_party_receipt_platform_aria_openapi_r1.py tests/test_honesty_defense_batch12_openapi_r1.py tests/test_printer_routing.py -q` passed 26 tests in 48.24s. Those tests use in-memory fixtures or source reads; `ribdigi_erp` was not opened. From `frontend`, `npx tsc --noEmit --pretty false --incremental false` exited 0. The open browser tab at `http://127.0.0.1:3000/` was the login form (Login tenant, Login email, Login password, Sign in). No password was entered. The signed-in POS, Sales, and Printers screens were not opened. A physical printer was not tested.
- Blocker: Signed-in click-through still needs an existing session. Do not type the drill password. A physical printer was not tested.

### T-UI-07 — Company settings can be finished section by section

- Priority: P1
- Requirement: A company administrator can finish profile, email, SMS, logo, print branding, tax, fiscal year, store allocation, and inactivity timeout on the Company page. Each section saves on its own. Blank optional fields are omitted. Suspension stays a note with no button and no reason field. Saving the profile still clears the cached date and number format.
- Module: `frontend/app/(dashboard)/company/page.tsx`, `frontend/app/globals.css` company-page rules, `frontend/lib/industries.ts`
- Dependencies: T-UI-02
- Status: Implemented awaiting verification
- Acceptance: Profile save does not send tax, fiscal year, or inactivity timeout. Email and SMS save do not reload the company profile. Store allocation has its own save. Narrow layout stacks in one column. Pharmacy is not in the new-company industry list. Relevant company tests pass and `tsc` exits 0. A signed-in company page is clicked through.
- Evidence: From `backend`, `PYTHONPATH=.` and Python 3.12 `pytest` of the company, tenant, formatting, print, staff-guide, profile, industry, and related source tests: **124 passed, 1 failed** in 165.87s (2026-10-14). The failure was `tests/test_industry_openapi_r1.py::test_industry_ui_and_docs` because `LEGACY_INDUSTRIES = ['pharmacy']` sat above `INDUSTRY_LABELS`. That constant was moved below the labels so a new company still chooses only retail, hotel, and restaurant, while an existing pharmacy company can still be labeled. Re-run of `tests/test_industry_openapi_r1.py`, `tests/test_company_page_sections_r1.py`, and `tests/test_company_industry_locked_r1.py`: **6 passed** in 4.87s. `npx tsc --noEmit --pretty false --incremental false` from `frontend` exited 0 after that move. The open browser at `http://localhost:3000/` was the login form. No password was entered. The signed-in Company page was not opened.
- Blocker: Signed-in click-through still needs an existing admin session. Do not type the drill password.

### T-UI-08 — POS selling path is readable

- Priority: P1
- Requirement: A cashier can search or scan, build a cart with readable quantity and price, then choose payment and charge. Customer name, cart discount, and coupon stay available without crowding Charge. Narrow screens use one column and scroll the cart list. Wide screens keep products beside the cart. Checkout still sends the cart on screen.
- Module: `frontend/app/(dashboard)/pos/page.tsx`, `frontend/app/globals.css` (`pos-ui-` rules), `frontend/components/Shell.tsx` (drawer class only)
- Dependencies: none
- Status: Implemented awaiting verification
- Acceptance: Existing POS aria-labels stay, including barcode search, payment method, cash and card tender, split tender, cart discount, customer, customer name, Charge complete sale, Clear POS cart, and Cash drawer open reason. Receipt paper control and the paper size Pay and Reprint send stay as the printer work left them. Cart discount and coupon each still use the full cart row, and the discount number keeps a 7.5rem floor. `npx tsc` exits 0. A signed-in POS screen is used on a wide and a narrow viewport.
- Evidence: File inspection of the POS page, shell topbar, and cart CSS. Qty controls were 22px, payment rows were 28px and nowrap, the cart was fixed at 85vh with overflow hidden between 481px and 980px, Pay used ellipsis, and Clear was an 11px share of the pay row. Drawer reason was capped at 40vw. Layout classes `pos-ui-` were added for search, cart lines, payment, amount due, and the topbar drawer. Customer name, discount, and coupon sit in a disclosure under Charge, still inside the cart dock. From `frontend`, `npx tsc --noEmit --pretty false --incremental false` exited 0. The browser at `http://127.0.0.1:3000/` was the login form (Login tenant, Login email, Login password, Sign in). No password was entered. The signed-in POS screen was not opened. 2026-10-14 follow-up left the `pos-ui-` layout and receipt-paper control in place. Catalog, cart, and saved-sales empty states are one next-step sentence. A multi-store cashier with no open shift can choose a store on the catalog, because that control had been inside the hidden header. From `frontend`, `npx tsc --noEmit --pretty false --incremental false` exited 0 again, and `npm run test:offline` passed 18. The same browser tab was still the login form. No password was entered. The cash drawer was not opened. Later the same day, only the helper paragraph under Receipt paper was removed. Checkout, the cart, split tender, offline selling, and the words New customer were left in place.
- Blocker: Signed-in click-through still needs an existing cashier session. Do not type the drill password. Do not open the cash drawer.

### T-UI-09 — Notifications, Backup, Security, Integrations, and AI assistance

- Priority: P1
- Requirement: Each screen puts the usual action first, folds advanced settings into a named section, and uses a one-sentence empty state that says what to do next. Narrow screens stack in one column. Existing aria-labels stay. Blank optional narrative fields stay null. Row actions use that row’s id. A failed backup is not described as successful. Chat stays fail-closed until AI is enabled.
- Module: `frontend/app/(dashboard)/notifications/page.tsx`, `frontend/app/(dashboard)/backup/page.tsx`, `frontend/app/(dashboard)/security/page.tsx`, `frontend/app/(dashboard)/integrations/page.tsx`, `frontend/app/(dashboard)/ai/page.tsx`, and the page CSS files `notify-ui.css`, `backup-ui.css`, `security-ui.css`, `integ-ui.css`, `ai-ui.css`
- Dependencies: none
- Status: Implemented awaiting verification
- Acceptance: Source tests that read these pages still pass. `npx tsc` exits 0. A signed-in visit of each screen is clicked through. No restore is applied to a database from this task.
- Evidence: 2026-10-14. Page CSS uses `notify-ui-`, `backup-ui-`, `security-ui-`, `integ-ui-`, and `ai-ui-`. `frontend/app/globals.css` was not edited. From `backend`, `PYTHONPATH=.` and `C:\Users\arthu\AppData\Local\Programs\Python\Python312\python.exe -m pytest` with `-k ui` on the notification, backup, security, integrations, AI, and honesty source tests that read these pages: one run reported 2 failed (`No API keys for this filter` and `No deliveries for this filter` had been reworded), those phrases were put back inside the next-step sentence, then **20 passed** in 10.45s and a further **11 passed** in 11.79s. Those tests read source or use in-memory fixtures. `ribdigi_erp` was not opened. No backup restore was run. From `frontend`, `npx tsc --noEmit --pretty false --incremental false` exited 0. The open browser at `http://127.0.0.1:3000/` was the login form (Login tenant, Login email, Login password, Sign in). No password was entered. The signed-in Notifications, Backup, Security, Integrations, and AI assistance screens were not opened.
- Blocker: Signed-in click-through still needs an existing session. Do not type the drill password. Do not apply a backup restore from the UI.

### T-UI-10 — Audit log is readable

- Priority: P1
- Requirement: The activity log comes first, with labeled filters beside it. What happened and record type are sent only when Apply filters is chosen. Export uses those same filters. A failed record check is not described as a success. Archive cold stays in its own section and still sends the policy days. Entries stay immutable.
- Module: `frontend/app/(dashboard)/audit/page.tsx`, `frontend/app/(dashboard)/audit/audit-ui.css`
- Dependencies: none
- Status: Implemented awaiting verification
- Acceptance: Existing audit aria-labels stay. Blank dates and a blank person are omitted. The empty state says what to do next. Narrow layout stacks the filters and scrolls the table. `npx tsc` exits 0. A signed-in Audit screen is opened. No cold archive is run against a live database.
- Evidence: File inspection of the Audit page. The log was below the retention card. Filters had no visible labels and sat in one row. Export sent the codes still being typed, and it called the API host directly with the raw tenant header. The table had a ninth cell under an eight-column header. A failed check used the green message line. Area choices omitted billing, printers, and restaurant. From `backend`, `PYTHONPATH=.` and `C:\Users\arthu\AppData\Local\Programs\Python\Python312\python.exe -m pytest` of the audit date, action, entity, module, retention, user-id, limit, and honesty source tests that read this page: **34 passed** in 32.48s (2026-10-14). Those tests use in-memory SQLite or source reads. `ribdigi_erp` was not opened. No cold archive was run. From `frontend`, `npx tsc --noEmit --pretty false --incremental false` exited 0. The open browser at `http://127.0.0.1:3000/audit` redirected to the login form (Login tenant, Login email, Login password, Sign in). No password was entered. The signed-in Audit screen was not opened.
- Blocker: Signed-in click-through still needs an existing session. Do not type the drill password. Do not run Archive cold now against a live database.

### T-UI-11 — Purchasing path is readable

- Priority: P1
- Requirement: The usual path is suppliers, then orders, then receive goods, then supplier bills, then returns. The open tab’s action comes first. Numbering and approval settings sit in a named section. Payments, balances, and history name the supplier. Existing aria-labels stay. Empty states are one sentence that says what to do next. Narrow screens stack in one column. Status words stay the API words. No local bill is marked paid and no payment gateway is called.
- Module: `frontend/app/(dashboard)/purchasing/page.tsx`, `frontend/app/(dashboard)/purchasing/purchase-ui.css`, supplier statement in `backend/app/credit.py`, and the payable party check in `frontend/app/(dashboard)/credit/page.tsx`
- Dependencies: none
- Status: Implemented awaiting verification
- Acceptance: Source tests that read the purchasing page still pass. `npx tsc` exits 0. A signed-in purchasing screen is opened and the path is clicked through. `ribdigi_erp` is not written from this task.
- Evidence: 2026-10-14. The page opened on Orders, with purchase requests between Suppliers and Orders. Numbering sat on the Orders toolbar and the approval matrix sat above Create purchase request. Payment and balance lived only on Credit, and a payable screen could keep a customer id or the first supplier. Receive goods reused the last opened order. A missing supplier showed an id fragment. Purchase history and the returns table could omit the supplier name. `supplier_statement` listed orders and payments and left out open supplier bills. Page CSS is `purchase-ui-` only. `frontend/app/globals.css` was not edited. Brand `#4AB012` was not changed. From `backend`, `PYTHONPATH=.` and `C:\Users\arthu\AppData\Local\Programs\Python\Python312\python.exe -m pytest` of the purchasing layout, soft-activate, GRN notes, supplier deactivate, numbering aria, party name, PO/PI/return/request status, honesty batch 5, and PO/PI/return/GRN notes tests: **4 failed, 40 passed** in 56.42s because the filter empty states no longer contained `No purchase orders for this filter`, `No purchase invoices for this filter`, `No purchase returns for this filter`, and `No purchase requests for this filter`. Those phrases were put back inside the next-step sentence. The four status UI tests plus `test_erp_friendly_layouts.py` then **5 passed** in 1.66s. Those tests read source or use in-memory fixtures. `ribdigi_erp` was not opened. No bill was marked paid. From `frontend`, `npx tsc --noEmit --pretty false --incremental false` exited 0. The open browser at `http://127.0.0.1:3000/purchasing` redirected to the login form (Login tenant, Login email, Login password, Sign in). No password was entered. The signed-in purchasing screen was not opened. Later the same day, a supplier name follows the purchase order when the bill or receipt has no matching supplier id, and the match is case-insensitive. Pay on a supplier bill includes that bill’s id. The payable form sends `purchase_invoice_id` only while the selected supplier still matches that bill; a different supplier pays oldest open bills. Viewing another bill clears a leftover OCR apply. The supplier list shows an open-bill count and amount from unpaid, partial, and overdue bills. Page CSS stays `purchase-ui-`. Brand `#4AB012` was not changed. From `backend`, `PYTHONPATH=.` and `C:\Users\arthu\AppData\Local\Programs\Python\Python312\python.exe -m pytest` of `test_erp_friendly_layouts.py`, `test_po_manage_status_openapi_r1.py`, `test_pi_manage_status_openapi_r1.py`, `test_pr_manage_status_openapi_r1.py`, `test_return_manage_status_openapi_r1.py`, `test_staff_guide_permission_s1.py`, and `test_ops_repairs_round.py::test_staff_guide_follows_industry_and_role`: **19 passed** in 26.82s. Those tests read source or use in-memory fixtures. `ribdigi_erp` was not opened. PINV-2026-0001 and PINV-2026-0002 were not marked paid. PO-2026-0002 was not received. From `frontend`, `npx tsc --noEmit --pretty false --incremental false` exited 0. The browser at `http://127.0.0.1:3000/purchasing` and `/support` redirected to the login form. No password was entered. The signed-in supplier and help screens were not opened.
- Blocker: Signed-in click-through still needs an existing session. Do not type the drill password. Do not write `ribdigi_erp` from this task.

### T-UI-12 — Inventory path is readable

- Priority: P1
- Requirement: The usual path is products, then categories, brands, and units, then variants, then stock (warehouse stock, adjust, count, history, low stock, expiry, batches). The open tab’s action comes first. Numbering sits in a named section. Existing aria-labels stay. Empty states are one sentence that says what to do next. Narrow screens stack in one column. Status words stay the API words. Adjust, count, and stock-out do not post against a previously selected product.
- Module: `frontend/app/(dashboard)/inventory/page.tsx`, `frontend/app/(dashboard)/inventory/inv-ui.css`
- Dependencies: none
- Status: Implemented awaiting verification
- Acceptance: Inventory layout source tests still pass. `npx tsc` exits 0. A signed-in inventory screen is opened and the path is clicked through. `ribdigi_erp` is not written from this task. Local stock counts are not marked complete.
- Evidence: 2026-10-14. The page listed eighteen peer tabs, and adjust, stock-out, expiry, opening, receive, and batch forms shared one selected product. Count drafts were keyed by product, so a second line for the same product could save the other line. Low stock and warehouse names used an uppercase clipped label. Expiry could send a made-up `LOT-YYYYMMDD` lot. Warehouse status said Out of stock / Low / OK instead of the API labels. Page CSS is `inv-ui-` only. `frontend/app/globals.css` was not edited. Brand `#4AB012` was not changed. From `backend`, `PYTHONPATH=.` and `C:\Users\arthu\AppData\Local\Programs\Python\Python312\python.exe -m pytest` of `test_inventory_stock_ui_friendly.py`, `test_catalog_manage_ui_friendly.py`, `test_out_of_stock.py`, `test_company_logo_and_low_stock_ui.py`, `test_erp_friendly_layouts.py`, `test_inventory_low_stock.py`, `test_stock_count_cancel_c1.py`, `test_category_variant_activate.py`, `test_brand_uom_activate.py`, `test_product_soft_deactivate.py`, and `test_soft_activate_btn_colors_r1.py`: **1 failed, 28 passed** in 53.32s. The failure is `test_inventory_and_pos_pages_label_out_of_stock` because `frontend/app/(dashboard)/pos/page.tsx` no longer contains `New customer`. Inventory still contains `Out of stock` and `stockStatusOf`. That POS file was not edited here. Those tests read source or use in-memory SQLite. `ribdigi_erp` was not opened. No stock count was marked complete. No purchase order was received. From `frontend`, `npx tsc --noEmit --pretty false --incremental false` exited 0. The open browser at `http://127.0.0.1:3000/inventory` redirected to the login form (Login tenant, Login email, Login password, Sign in). No password was entered. The signed-in inventory screen was not opened. After the empty-state wording, `test_inventory_stock_ui_friendly.py` and `test_catalog_manage_ui_friendly.py` passed again: **2 passed** in 1.58s.
- Blocker: Signed-in click-through still needs an existing session. Do not type the drill password. Do not write `ribdigi_erp` from this task. Do not mark a local stock count complete. Later the same day, `New customer` was present again in `frontend/app/(dashboard)/pos/page.tsx`, and `tests/test_out_of_stock.py::test_inventory_and_pos_pages_label_out_of_stock` passed inside a 43-test sales and POS source run.

### T-UI-13 — Sales path is readable

- Priority: P1
- Requirement: The usual path is customers, then quotes, then orders, then invoices, then returns. Coupons and gift cards are codes on that path. The open tab’s action comes first. Numbering sits in a named section. Existing aria-labels stay. Empty states are one sentence that still contains the filter phrases source tests require. Narrow screens stack in one column. Pay uses the clicked invoice row’s id and that row’s typed amount. Gift cards do not debit cash 1000 and do not charge a bank card.
- Module: `frontend/app/(dashboard)/sales/page.tsx`, `frontend/app/(dashboard)/sales/sales-ui.css`
- Dependencies: none
- Status: Implemented awaiting verification
- Acceptance: Source tests that read the sales page still pass, including the out-of-stock page label test. `npx tsc` exits 0. A signed-in sales screen is opened and the path is clicked through. `ribdigi_erp` is not written from this task. No local invoice is marked paid.
- Evidence: 2026-10-14. The page opened on All sales, and New mixed customer groups with quote, order, and invoice save. Numbering was wrapped in `{false &&}` so the prefix fields never rendered. Pay used one shared amount and selected the invoice while typing, so another row could send a blank amount. Coupons and gift cards did not say what the code does. Page CSS is `sales-ui-` only. `frontend/app/globals.css` was not edited. Brand `#4AB012` was not changed. Gift card issue still calls `POST /gift-cards`; liability accounts 2150 and 2160 were not changed. From `backend`, `PYTHONPATH=.` and `C:\Users\arthu\AppData\Local\Programs\Python\Python312\python.exe -m pytest` of the sales layout, quotation, order, invoice, and return status and notes tests, numbering aria, print query, discount UI, honesty batches 21 and 30, `test_out_of_stock.py::test_inventory_and_pos_pages_label_out_of_stock`, and `test_pos_till_scan_print_r1.py::test_pay_prints_receipt_once`: **43 passed** in 49.95s. Those tests read source or use in-memory fixtures. `ribdigi_erp` was not opened. No invoice was marked paid. From `frontend`, `npx tsc --noEmit --pretty false --incremental false` exited 0. The open browser at `http://127.0.0.1:3000/sales` and `http://127.0.0.1:3000/pos` redirected to the login form (Login tenant, Login email, Login password, Sign in). No password was entered. The signed-in sales and POS screens were not opened.
- Blocker: Signed-in click-through still needs an existing session. Do not type the drill password. Do not write `ribdigi_erp` from this task. Do not mark a local invoice paid.

## Security, recovery, and release

### T-SEC-01 — Secrets and production boundary

- Priority: P0
- Requirement: No secrets in source, logs, or client bundles. No production or staging migrate, restart, password reset, real charge, queue deletion, push, or deploy without authorization.
- Module: repo-wide
- Dependencies: none
- Status: In progress
- Acceptance: This session does not perform those actions. `.env` is not committed by this work.
- Evidence: No production database operation in this planning pass. Pytest fixtures are in-memory SQLite (`backend/tests/conftest.py`).
- Blocker: Ongoing constraint, not a code defect.

### T-REC-01 — Backup restore rehearsal

- Priority: P1
- Requirement: Restore is proven on an isolated database. `ribdigi_erp` is not overwritten.
- Module: `docs/DR_LOGICAL_BACKUP_RUNBOOK.md`
- Dependencies: T-SEC-01
- Status: Implemented awaiting verification
- Acceptance: A disposable restore matches counts and has no unbalanced journals, then the drill database is dropped.
- Evidence: Report records restore into `ribdigi_restore_drill` in 16.57s, matching counts, then drop. Not a production backup. Not repeated here.
- Blocker: none

### T-REL-01 — Release honesty

- Priority: P0
- Requirement: General release. Not certified. Not Offline Complete. Historical 2026-10-05 “Not ready for market” stays.
- Module: `docs/COMMERCIAL_READINESS_REPORT.md`, `docs/OFFLINE_POS.md`, `docs/RETAIL_FEATURE_MATRIX.md`
- Dependencies: T-OFF-02
- Status: Done
- Acceptance: The 15 October 2026 UTC lead says general release, not certified, and not Offline Complete. `offline_complete_claimed` stays false. The 2026-10-05 paragraph is unchanged.
- Evidence: `docs/COMMERCIAL_READINESS_REPORT.md` and `docs/RETAIL_FEATURE_MATRIX.md` lead with that sentence. `backend/app/offline_pos.py` still returns `offline_complete_claimed` false.
- Blocker: Certification, a live site, and Offline Complete are not done. That is expected.
