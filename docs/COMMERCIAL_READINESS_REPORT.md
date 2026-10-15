# RIBDIGI ERP COMMERCIAL READINESS REPORT

**Date:** 2026-09-17 (historical scorecard). **15 October 2026 UTC** is the latest result. Earlier addenda stay below. The 2026-10-05 section still says **Not ready for market**.

## 15 October 2026 UTC

**General release. Not certified. Not Offline Complete.** Offline POS is **Ready**. `offline_complete_claimed` stays false. Hotel and restaurant stay Not ready. Security is Ready and not Verified. The live site, the full backend suite, and an external test were not run. This pass did not commit, push, deploy, migrate, charge a payment, reset a password, sign in `cashier@offline-drill-oct13.example`, close `SHIFT-2026-0001`, `SHIFT-2026-0002`, or `SHIFT-2026-0007`, mark `PINV-2026-0001` or `PINV-2026-0002` paid, or receive `PO-2026-0002`. `ribdigi_erp` was not overwritten. The 2026-10-05 section still says **Not ready for market**.

| Area | Status | Evidence |
| --- | --- | --- |
| Security | Ready | Auth, isolation, 2FA, uploads, billing identity, cashier presence, and the store-scoped staff list passed in memory: **123 passed** in 285.97s. Unsigned visits to `/security` and `/pos` on `http://127.0.0.1:3000` returned to the login form. This is not Verified and not certified. A signed-in browser session, the live site, the full backend suite, and an external test were not executed. |
| Retail | Ready | One signed-in cashier sale on the disposable test company posts stock 20 to 18, cash 220 on account 1000, one balanced journal, the same sale on replay, a receipt total of 220, and a daily report `pos_revenue` and `total_revenue` of 220. A cashier still cannot record a supplier payment. The local company database was not used for that sale, and nobody signed in through the browser. Multi-store was not walked. |
| Offline POS | Ready | `frontend` `npm run test:offline`: **21 passed**, 0 failed. That covers prepare, a queued cash sale, closing the browser database, reading the sale back, and one replay of the same `client_request_id`. This is not Offline Complete. A closed browser still cannot be promised to upload. The device id is not strong binding. A private window with no till-agent journal cannot recover sales. Wallet, gift card, and loyalty stay online-only. Credit stays on the server-reviewed queue. `offline_complete_claimed` stays false. |
| Hotel | Not ready | Not tested in this pass. |
| Restaurant | Not ready | Not tested in this pass. |

### Verified fixes

- A signed billing webhook must include the company, the amount, and the currency. Omitting any of those leaves the invoice unpaid and does not save a reusable authorization. Checkout and charge send the company id in provider metadata. Paystack and Flutterwave host locks are unchanged.
- Cashier presence and `GET /users` follow store membership. A manager assigned to one store does not see another store's cashier email, shift totals, or staff record. Asking for the other store returns 403. A company admin still sees both. A manager with no membership still sees the company. Staff with no store membership stay visible inside the company.
- `POST /suppliers/{supplier_id}/payments` now requires `credit:read` as well as `credit:write`. Till credit is `credit:write` only, so a cashier is refused. From `backend`, `PYTHONPATH=.`, `RATE_LIMIT_BACKEND=memory`, Python 3.12, no `--timeout`: `pytest tests/test_cashier_pos_only.py -q --tb=short`. Result: **4 passed** in 6.44s, exit 0. The cashier post returned 403. The company-admin post to a supplier that does not exist returned 404, so the extra check did not lock out an administrator. In-memory SQLite. `ribdigi_erp` was not opened by pytest.
- Offline queue: prepare a grant, queue a cash sale, close IndexedDB, read the sale back, flush once, flush again. The fake API is called once, with the same `client_request_id`, and one row is synced. From `frontend`: `npm run test:offline`. Result: **21 passed**, 0 failed, exit 0. That includes “offline complete stays missing” and the till-journal read-back after IndexedDB is cleared. `offline_complete_claimed` in `backend/app/offline_pos.py` is still false.
- Retail sale chain: stock 20, cost 60, exclusive price 100, tax 10% (test fixture), sell 2. Receipt total 220, thermal text contains 220, remaining stock 18, cash debit 1000 equals 220, one journal, debits equal credits at 340, replay of `retail-arith-220-001` returns the same sale, and the company-admin daily sales report shows `pos_revenue` and `total_revenue` 220. From `backend`, `PYTHONPATH=.`, `RATE_LIMIT_BACKEND=memory`, Python 3.12, no `--timeout`: `pytest tests/test_retail_pos_arithmetic_fixture.py -q --tb=short`. Result: **1 passed** in 6.25s, exit 0. In-memory SQLite. `ribdigi_erp` was not opened.

### Commands and results — local restore drill

This is a local copy of `ribdigi_erp`. It is not a production restore and not an authorized `.ribbak` restore. Tool version inside `ribdigi-erp-postgres-1`: `pg_dump` and `pg_restore` **PostgreSQL 16.14**. Role `ribdigi`. No password was printed.

1. `docker exec ribdigi-erp-postgres-1 psql -U ribdigi -d ribdigi_erp -c "SELECT current_database();"` returned `ribdigi_erp`.
2. `docker exec ribdigi-erp-postgres-1 pg_dump -U ribdigi -d ribdigi_erp -Fc --no-owner --no-acl -f /tmp/ribdigi_drill_20261015.dump` wrote 1007203 bytes. The dump file was inside the container, outside the application database.
3. The name `ribdigi_drill_20261015` was checked against `ribdigi_erp`, `production`, and `staging`, then created. `current_database()` on it returned `ribdigi_drill_20261015`.
4. `docker exec ribdigi-erp-postgres-1 pg_restore -U ribdigi -d ribdigi_drill_20261015 --no-owner --no-acl --exit-on-error /tmp/ribdigi_drill_20261015.dump` exited 0.
5. On the disposable database: users 9, tenants 6, sales 40, journal entries 50. Those counts matched a following read-only count on `ribdigi_erp` after `current_database()` again returned `ribdigi_erp`. Users, journals, sales, and stock rows without a tenant: 0. Journal or stock rows whose creator belongs to another tenant: 0. Sales belonged to 3 tenants.
6. `DROP DATABASE ribdigi_drill_20261015` from database `postgres`, then the dump file was removed. A later list no longer contains that name. `current_database()` on `ribdigi_erp` still returned `ribdigi_erp`.

### Failed checks

None in the cashier file, the offline suite, or the 15 October security command below.

### Commands and results — local security

From `backend`, `PYTHONPATH=.`, `RATE_LIMIT_BACKEND=memory`, Python 3.12, no `--timeout`: auth sessions, login 2FA, WebAuthn, tenant isolation, tenant isolation matrix, attachment paths, user-store RBAC, staff-guide permission, offline POS isolation, security middleware, OWASP smoke, OWASP O1, OWASP T1, expense attachments, product images, brand logo, subscription billing, billing gateways, and cashier presence. Result: **123 passed** in 285.97s, exit 0. In-memory SQLite. `ribdigi_erp` was not opened. Live health was not requested.

### Not run

- Signed-in retail multi-store walkthrough.
- Signed-in hotel walkthrough.
- Signed-in restaurant walkthrough.
- Full backend suite. The named auth, isolation, 2FA, upload, billing, and presence files were re-run (123 passed). The rest of the backend suite was not.
- Live `https://erp.ribdigihouse.com/api/v1/health`.
- External penetration test.
- Browser-closed upload, private-window recovery without the till-agent journal, and strong device binding.
- A production or `.ribbak` restore.

### Environmental blockers

- The browser at `http://127.0.0.1:3000/` is the login form. Unsigned `/security` and `/pos` return there. The drill cashier was not signed in. No password script was written. No sale was written to `ribdigi_erp`.

### Accepted operating limitations

- A closed browser is not guaranteed to upload a queued sale. Private browsing and cleared site data cannot recover the queue unless the till-agent journal was running when the sale was saved. A browser device id is not strong device binding. The service worker does not cache `/api/`.
- Wallet, gift card, and loyalty stay online-only. Credit stays on the server-reviewed queue.
- A sales officer who already has `credit:read` and `credit:write` can still record a supplier payment. An inventory officer still cannot, because that role has no credit permission.
- `offline_complete_claimed` stays false.
- Paystack and Flutterwave host locks, secret prefix checks, and the unpaid-until-signed-confirmation rule were not loosened. Brand `#4AB012` was not changed. New-company industries remain retail, hotel, and restaurant. FMCG was not restored.

### Code changed in this pass

`backend/app/api.py` (supplier payment requires `credit:read`; staff list follows store membership), `backend/tests/test_cashier_pos_only.py` (cashier 403 and company-admin 404), `backend/tests/test_retail_pos_arithmetic_fixture.py` (receipt and daily report on the same sale), and `frontend/lib/posOfflineQueue.test.ts` (restart then one replay). Customer payment and POS credit were not narrowed.

## 2026-10-14 evening reassessment

**Not a general release. Not certified. Not Offline Complete.** `offline_complete_claimed` stays false. This pass did not commit, push, deploy, migrate, or write `ribdigi_erp`. `backend/app/api.py` and `tests/test_pos_sale_replay_r1.py` were not edited. Replay stays with the other pass.

| Area | Status | Why it did not move |
| --- | --- | --- |
| Security | Blocked | The previously unexecuted auth, permission, isolation, 2FA, upload, and hotel cross-tenant tests passed after one login-copy repair. The full backend suite, a signed-in walkthrough, the live site, an external test, and an authorized restore were not executed. |
| Retail | Not ready | `http://127.0.0.1:3000/` is the login form. No signed-in single-store or multi-store walkthrough. |
| Offline POS | Incomplete | `npm run test:offline` passed 20. A closed browser still cannot be promised to upload. The device id is not strong binding. A private window with no till-agent journal cannot recover sales. |
| Hotel | Not ready | Hotel API tests passed in memory. No signed-in hotel walkthrough. |
| Restaurant | Not ready | No signed-in restaurant walkthrough. |

### Verified fixes

- Login, when the health probe is still online but the sign-in request cannot reach the server, shows `unreachableApiMessage('/auth/login')`. A leftover `X-Tenant-ID` still does not choose the workspace. Re-run: `tests/test_login_stale_session_header_l1.py` **3 passed** in 6.36s. In-memory SQLite. `ribdigi_erp` was not opened.
- Gift-card and loyalty issue, redemption, refund, and reversal stay on 2150, 2160, 6100, and 6110. An inactive bank account 1010 rejects card and Mobile Money instead of debiting till cash 1000. An inactive loyalty account 2160 rejects that tender even when a cash account id is sent. Drawer expected cash for a split of cash 4, Mobile Money 11, and bank transfer 15 is opening cash plus 4 only. Forged and cross-company account ids stay 404. The file now has 10 tests. They passed inside the combined run below. No change was required in the sale-replay section of `api.py`.

### Commands and results

From `backend`, `PYTHONPATH=.`, `RATE_LIMIT_BACKEND=memory`, Python 3.12, no `--timeout`: password reset, email verification, stale login header, TOTP, 2FA code and disable-password OpenAPI, users and roles, custom roles, cashier POS limits, backup restore isolation, storage, product import, user import, expense OCR, purchase OCR, company logo, attachment preview, hotel and FMCG security audit, and payment GL routing. First result: **1 failed, 99 passed**, 1502 warnings, 201.44s, exit 1. The failure was `test_login_client_omits_stale_session_headers` because the login page no longer called `unreachableApiMessage('/auth/login')`. After that call was restored, the login file passed as above. The other 99 were not re-run after the repair. Those tests use in-memory SQLite. `ribdigi_erp` was not opened. Rate-limit tests were not in this command; they remain the earlier same-day result inside `tests/test_security_middleware.py` (part of the 99 passed in 210.51s).

From `frontend`: `npm run test:offline`. Result: **20 passed**, 0 failed, 1165ms, exit 0. That run includes “offline complete stays missing” and “queued sale is read back from the till journal after IndexedDB is cleared”.

`GET http://127.0.0.1:3000/` returned 200. The HTML contains Login tenant, Login email, Login password, and Sign in. No password was entered. The drill cashier was not signed in. The Docker frontend image was not rebuilt, so this browser tab does not show the login-copy edit.

### Failed checks

None remain in the commands above after the login-copy repair. The first combined run failed one source assertion, which was repaired and re-run.

### Not run

- Signed-in retail single-store walkthrough.
- Signed-in retail multi-store walkthrough.
- Signed-in hotel walkthrough.
- Signed-in restaurant walkthrough.
- Full backend suite.
- Live `https://erp.ribdigihouse.com/api/v1/health`.
- A second proof of two POS inserts at the same moment. That replay file was left to the other pass.
- Browser-closed upload, private-window recovery, and strong device binding.

### Environmental blockers

- Isolated PostgreSQL restore: **Blocked**. `docker exec ribdigi-erp-postgres-1` reports `psql`, `pg_dump`, and `pg_restore` PostgreSQL 16.14. The backend mount `/data/backups` is Docker volume `ribdigi-erp_backup_data` and `ls -la` shows only `.` and `..`. No `.ribbak`, `.dump`, or `.backup` file was found in this tree. No disposable database was created. `ribdigi_erp` was not dumped and was not overwritten.

### Accepted operating limitations

- A gift-card refund credits liability 2150. It does not restore the plastic card balance.
- A closed browser is not guaranteed to upload a queued sale. Private browsing and cleared site data cannot recover the queue unless the till-agent journal was running when the sale was saved. A browser device id is not strong device binding.
- Drawer expected cash does not include gift card, loyalty, card, Mobile Money, or bank transfer.
- `offline_complete_claimed` stays false.

### Code changed in this pass

`backend/tests/test_payment_gl_routing.py` (inactive bank and loyalty accounts, and a non-cash drawer total) and `frontend/app/page.tsx` (login unreachable-server copy). Paystack and Flutterwave host locks, secret prefix checks, and the unpaid-until-signed-confirmation rule were not loosened. Brand `#4AB012` was not changed. FMCG was not restored as a new-company industry.

## 2026-10-14 later reassessment

**Not a general release. Not certified. Not a verified live site.** `offline_complete_claimed` stays false.

| Area | Status | Why it did not move |
| --- | --- | --- |
| Security | Blocked | Named auth, isolation, 2FA, rate-limit, upload, job, and infra tests passed. The full suite, a signed-in walkthrough, the live site, and an authorized restore were not executed. |
| Retail | Not ready | Single-store and multi-store signed-in walkthroughs were not run. |
| Offline POS | Incomplete | In-memory replay and the till-agent journal file passed. A closed browser still cannot be promised to upload. The device id is not strong binding. |
| Hotel | Not ready | No signed-in hotel walkthrough. |
| Restaurant | Not ready | No signed-in restaurant walkthrough. |

### Verified fixes

- Gift-card and loyalty issue, redemption, refund, and reversal stay on 2150, 2160, 6100, and 6110. A cash account id on those tenders does not post till cash. A split tender’s drawer cash is only the cash portion. A cross-company account id and a forged id return 404. A revenue account id and a non-cash refund aimed at till cash return 400. The 9 tests in `tests/test_payment_gl_routing.py` passed inside the combined run whose only failures were the two replay tests named below. In-memory SQLite. `ribdigi_erp` was not opened.
- A lost POS response with the same `client_request_id` returns the original sale: one tender set, one stock movement, one journal. A different quantity, including an offline sale and a queued quote, returns HTTP 409 `CLIENT_REQUEST_REUSED`. A missed lookup that then hits the unique key returns the original sale. Two retries after the sale is committed both return that sale. Command from `backend`, `PYTHONPATH=.`, Python 3.12: `pytest tests/test_pos_sale_replay_r1.py tests/test_pos_sale_client_request_id_idempotent.py tests/test_offline_pos_grants.py::test_offline_quote_capture_is_idempotent -q --tb=line`. Result: **7 passed** in 32.03s. The first run of the two overlapping-insert tests returned “That record already exists.” The flush handler was then taught to wait for the winning sale. Two inserts at the same moment still share this fixture’s one SQLite connection, so that shape was not claimed as a second proof.
- Till-agent journal: `pytest tests/test_pos_offline_journal_r1.py -q --tb=line --noconftest` from `backend`. Result: **4 passed** in 0.70s. The same `client_request_id` keeps the original payload. A later write does not replace the commercial terms. Password fields are not stored in the file.
- Security command from `backend`, `PYTHONPATH=.`, `RATE_LIMIT_BACKEND=memory`, Python 3.12, no `--timeout`: auth sessions, login 2FA, WebAuthn, tenant isolation, tenant isolation matrix, attachment paths, user-store RBAC, staff-guide permission, offline POS isolation, security middleware, OWASP smoke, OWASP O1, OWASP T1, expense attachments, product images, and brand logo. Result: **99 passed** in 210.51s, exit 0. Those rate-limit tests call `rate_limiter.reset_for_tests()`. Job path and tenant infra privacy: **10 passed** in 32.15s, exit 0.

### Failed checks

None in the commands above after the replay flush fix. The first replay run failed two tests with HTTP 409 detail “That record already exists.” That was repaired and the replay file then passed.

### Not run

- Signed-in retail single-store walkthrough.
- Signed-in retail multi-store walkthrough.
- Signed-in hotel walkthrough.
- Signed-in restaurant walkthrough.
- One live retail sale reconciled from receipt through report. The earlier read-only check of `POS20260036` was not repeated.
- Frontend `npm run test:offline`. Offline frontend code was not changed. The prior result remains 20 passed.
- Full backend suite.
- Live `https://erp.ribdigihouse.com/api/v1/health`.

`GET http://127.0.0.1:3000/` returned 200. The HTML contains Login tenant, Login email, and Sign in. No non-drill test credential was already known. The drill cashier was not signed in. No password was printed.

### Environmental blockers

- Isolated PostgreSQL restore: **Blocked**. Client tools inside the already-running `ribdigi-erp-postgres-1` are `psql`, `pg_dump`, and `pg_restore` PostgreSQL 16.14. `/data/backups` on `ribdigi-erp-backend-1` is empty. No `.ribbak` file was in this tree. No disposable database was created. `ribdigi_erp` was not dumped and was not overwritten.

### Accepted operating limitations

- A gift-card refund credits liability 2150. It does not restore the plastic card balance. A sales return has no card-code column, and no migration was added.
- A quote retry that omits `unit_price` matches the stored quote. The first request’s override price is not compared, because a quotation has no stored fingerprint and no migration was added.
- A closed browser is not guaranteed to upload a queued sale. Private browsing and cleared site data cannot recover the queue unless the till-agent journal was running when the sale was saved. A browser device id is not strong device binding.
- Drawer expected cash does not include gift card, loyalty, card, Mobile Money, or bank transfer.

### Code changed in this pass

`backend/app/accounting.py` refund routing, `backend/app/api.py` sale and quote replay, `backend/app/schemas.py` comment, `backend/tests/test_payment_gl_routing.py`, and new `backend/tests/test_pos_sale_replay_r1.py`. Paystack and Flutterwave host locks, secret prefix checks, and the unpaid-until-signed-confirmation rule were not loosened. Brand `#4AB012` was not changed.

## 2026-10-14 addendum (security and money review)

**Not a general release. Not certified.** `offline_complete_claimed` stays false. This pass did not deploy, commit, or write `ribdigi_erp`.

### What changed

A gift-card or loyalty tender that also sent a cash-account id could post that cash account. The sale path now drops that account id for gift card and loyalty, and the journal still debits 2150 or 2160. Mobile Money, card, and bank transfer still refuse a till-cash account id (`1000`) with HTTP 400. Issuing a gift card still debits expense 6100 and credits 2150, because that screen does not collect money. Selling a card for cash is not a separate posting. That policy is unresolved and was not reclassified.

### Verified in this pass

- `tests/test_payment_gl_routing.py`: **6 passed** in 15.87s, including the new cash-account override case. In-memory SQLite. `ribdigi_erp` was not opened by pytest.
- Dashboard purchases: `tests/test_dashboard.py::test_dashboard_purchases_count_recorded_bills_not_drafts` **passed** in the 2-test run (6.01s). Recorded bills are unpaid, partial, paid, and overdue. Drafts stay out. Purchase orders are not added on top of bills.
- Last active company admin: `tests/test_users_roles.py::test_last_company_admin_cannot_be_deactivated_or_reassigned` **passed** in that same run.
- Alembic script heads: `['20261011_0138']` only.
- Read-only on `127.0.0.1`, after `current_database()` returned `ribdigi_erp`: 0 duplicate `(tenant_id, client_request_id)` pairs, 0 unbalanced journals. Sale `POS20260036` is one completed row, total 5.75, tax 0.75, one cash tender 5.75, one stock-out of 1, one posted journal (debit 7.75, credit 7.75: cash 1000 5.75, COGS 5000 2.00, inventory 1200 2.00, revenue 4000 5.00, tax 2100 0.75). A lost-response replay was not executed. `SHIFT-2026-0001`, `SHIFT-2026-0002`, and `SHIFT-2026-0007` were not updated.
- `http://127.0.0.1:3000/` was the login form. No password was entered.

### Not run or blocked

- Signed-in retail, hotel, and restaurant walkthroughs: **Not run**.
- Offline queue suite: **Not run** in this pass. Offline Complete stays missing.
- Live `https://erp.ribdigihouse.com/api/v1/health`: **Not run**.
- Isolated restore: **Blocked**. `pg_dump` and `pg_restore` are not on PATH. No disposable database was created. `ribdigi_erp` was not restored over.

## 2026-10-13 addendum (retail count-and-close)

**Ready for market. Not certified.** Retail can be sold as a controlled release from this tree. Certification still needs the checks listed below. Offline scope stays offline POS. `offline_complete_claimed` stays false.

### What changed

- Shift report on POS now records counted cash and closes that open shift. A difference requires a short note. Pending offline sales for that shift block the close. Sign-out still closes at the expected drawer amount.
- Gift-card and loyalty redemption no longer debit cash account 1000. A gift card posts to liability 2150. Loyalty points post to liability 2160. Issuing a card debits expense 6100 because that screen does not collect money. A named customer earns 1% of the sale, and that award debits expense 6110 and credits 2160. A walk-in earns no points.

### Verified in this pass

- `tests/test_pos_cash_movements.py`: **3 passed** in 8.20s (cash in/out variance, cashier cannot close another shift, counted-cash control present and sign-out still uses expected cash). Frontend typecheck was run separately.
- The 120-case retail checklist is not in this repository. It was not run.
- Signed-in browser walkthrough was not run. No password was entered.
- Isolated Postgres restore is recorded in the later checks below.

### 2026-10-13 later checks

- Unreachable API copy now says the device is offline or the server did not respond, and it tells the user to reconnect. Sign-in still cannot succeed while disconnected. Pending Point of Sale sales stay on the device until sync succeeds.
- Arithmetic fixture on a disposable test database: opening stock 20, unit cost 60, tax-exclusive price 100, tax 10%, quantity 2. Result: total 220, subtotal 200, tax 20, cash debit 220, revenue credit 200, tax credit 20, COGS debit 120, inventory credit 120, stock left 18, one journal. Repeating the same `client_request_id` returned the original sale. `tests/test_retail_pos_arithmetic_fixture.py`: **1 passed** in 6.00s. `tests/test_pos_sale_client_request_id_idempotent.py` passed in the same session. The 10% rate is a test fixture, not tax guidance.
- Last active company admin: soft deactivate, role change, and delete are refused while that person is the only active company admin. After a second company admin exists, the original admin can be reassigned. `tests/test_users_roles.py` plus `tests/test_users_delete_account_r1.py`: **6 passed** in 20.67s.
- Isolation, store caps, offline POS sync, and subscription billing: **57 passed** in 178.39s (`test_tenant_isolation_matrix.py`, `test_subscription_store_limits_r1.py`, `test_offline_pos_isolation.py`, `test_saas_billing_r1.py`).
- Local Postgres restore rehearsal: `pg_dump` of `ribdigi_erp` restored into a new database `ribdigi_restore_drill` in 16.57s. Counts matched the source (tenants 5, users 7, products 3, transactions 35, journal entries 36, stock movements 42). Every company had zero unbalanced journals. The drill database was dropped. The app database was not overwritten. This was a local copy, not a production backup file.
- Sales documents, cashier POS limits, and stores: **12 passed** in 8.69s (`test_sales_docs.py`, `test_sales.py`, `test_cashier_pos_only.py`, `test_stores.py`).
- Gift cards and loyalty: a named sale earns 1% and posts liability 2160, not cash. POS collects **Gift card code** only when the tender is a gift card and sends that code as the tender reference. There is no general payment-reference box. Gift-card code, loyalty earn, and cash-routing checks: **5 passed** in 14.15s.

### Not certified until

- Signed-in single-store and multi-store retail walkthrough beyond this one POS sale.
- Live site was not tested.
- One local offline POS sale was walked on company `offline-drill-oct13`: prepare online, disconnect, sell cash, reload, reconnect, sync. Sale, stock, balanced journal, tender, and open shift totals matched. Offline mode is not certified.
- The company dashboard lists each cashier as a card: online or offline, store, open shift, and sales waiting to sync. Offline POS remains the only offline surface. `offline_complete_claimed` stays false.
- Offline Complete remains missing because the browser device id is not strong device binding, a private window with no till-agent journal on this PC cannot recover those sales, saved sales upload only while the Point of Sale page is open and signed in, and a live site has not been tested.

## 2026-10-05 addendum (local production tree)

**Not ready for market.** The full backend suite is green. The isolated Postgres restore and the signed-in browser walkthrough are still open. `offline_complete_claimed` stays false. Offline scope is offline POS only.

### Verified

- Targeted behavioral slice: 38 passed, exit 0, ended 2026-10-04T23:59:14Z.
- Isolated sqlite restore: 2 passed, 5.44s. Create, dry-run, apply, verify. Not a Postgres restore.
- Frontend build after the UI contract edits: Next.js 14.2.35, 44/44 pages, exit 0, ended 2026-10-05T02:25:52Z. Brand green `#4AB012` is unchanged. The `themeColor` metadata warning is cleared by keeping the color on `viewport` only.
- Full backend pytest: **2855 passed, 1 skipped**, 36257 warnings, 4345.20s, exit 0, ended 2026-10-05T10:09:14Z. Command: `PYTHONPATH=.` and `python -m pytest -q --tb=line` from `backend` on Python 3.12.10. Prior counts kept for the trail: 112 failed / 2743 passed (2026-10-04T23:25:55Z), then 1 failed / 2854 passed (2026-10-05T04:53:20Z).
- Authenticated load smoke, same 2000ms target. Focused command: `python -m pytest tests/test_loadtest_baseline_l1.py::test_baseline_authenticated_scenarios_asgi -q --tb=line` (concurrency 3, 5 iterations, login + products + dashboard). Idle: login p50 469.62ms / p95 604.73ms, products p95 592.36ms, dashboard p95 462.47ms, run 2454ms, 1 passed in 5.43s. With eight busy CPU processes: login p95 593.89ms, products p95 524.31ms, dashboard p95 473.72ms, 1 passed in 5.55s. The full suite above includes this test. Measured cause of the 2526.3ms miss: bcrypt cost 12 (`verify_password` about 240ms) ran on the asyncio event loop, so three concurrent verifies finished at 256ms, 523ms, and 734ms. The same three calls on worker threads finished together near 230ms. Login, disable-2FA, and change-password now use `asyncio.to_thread`. Hash rounds, rate limits, audit, and the 2000ms target were not changed.

### Blocked

- Isolated Postgres restore. Listener 127.0.0.1:5432 is the live app database `ribdigi_erp` only. No disposable database and no `.ribbak`. See the operator steps in `docs/DR_LOGICAL_BACKUP_RUNBOOK.md`.
- Browser sign-in and on-screen receipt preview. Login form is up at `http://127.0.0.1:3000/` on the Docker frontend image. Password was not entered. API walkthroughs do not close this gate.
- `metadataBase` warning remains because no public site origin is configured.

### Owner tasks (still incomplete)

Production HTTPS, secrets, workers, load certification, and physical POS checks.
  
**Code HEAD (this workstream):** see branch `production`  
**Principle:** No false completion. Automation cannot execute physical POS / VPS / pen tests.

## 2026-10-04 QA addendum (local production tree)

Go-live remains **NOT READY**. The full backend suite on this tree failed. Isolated sqlite restore and the signed-in API walkthrough are recorded in `docs/GO_LIVE_CHECKLIST.md`. A production database was not restored. Offline POS is the only offline surface; the rest of the ERP is online-only. `offline_complete_claimed` stays false.

| Check | Result |
|-------|--------|
| Isolated sqlite backup/restore | PASS — 2 passed in 5.44s. Create, dry-run validate, apply, verify. Other tenant untouched. Queued offline sales remain and can be dismissed. Store and warehouse ownership restored. Failed proof returns 409 and leaves no partial product or store name. |
| Frontend production build | PASS — `npm run build` in `frontend`, Next.js 14.2.35, 44/44 pages, exit 0 (2026-10-04T21:59:44Z). |
| Signed-in retail and pharmacy, single and multi | PASS (API) — POS shift, Mobile Money sale, receipt, daily sales report, single-store transfer 403, multi-store transfer 200, pharmacy dashboard desk, expired and quarantined lots 409. Browser password entry was not driven. |
| Full backend pytest | FAIL — 112 failed, 2743 passed, 1 skipped, 35745 warnings, 3631.66s, exit 1. Sampled failures match clean HEAD. Not a missing-service result. |

---

## Scorecard

| Area | Verdict |
|------|---------|
| Architecture | **PASS** (shared schema + `tenant_id`; Tenant == Company profile for MVP) |
| Tenant Isolation | **PASS** |
| Multi-Company | **PARTIAL** — 1 Company profile per Tenant by design; child Companies **POST-MVP** |
| Company Entitlement | **PARTIAL** — `max_companies` informational (=1); store entitlements authoritative |
| Store Entitlement | **COMPLETE** |
| User ↔ Store Assignment | **COMPLETE** (membership model + POS enforcement; empty = grandfather all) |
| RBAC | **PASS** |
| Inventory | **PASS** |
| Purchasing | **PASS** |
| Sales | **PASS** |
| POS (online) | **PASS** |
| Accounting | **PASS** |
| Tax | **PASS** |
| Credit | **PASS** |
| Offline Foundation | **PARTIAL** (IndexedDB queue + 7-day envelope + idempotent `client_request_id`; endurance/device certification NOT RUN) |
| 7-Day Offline | **NOT RUN** (auth window implemented; physical 7-day endurance not executed) |
| Offline Recovery | **PARTIAL** (JSON export/import of pending queue + envelope metadata; no secrets; physical recover drill NOT RUN) |
| POS Device Monitoring | **PARTIAL** (`pos_devices` heartbeat upsert + list API; no alert dashboard / MDM) |
| POS Device Lockdown | **PARTIAL** (app cash-offline rules + reset guard; OS guide in `docs/POS_DEVICE_LOCKDOWN_GUIDE.md`; physical kiosk verification NOT RUN) |
| Windows / Android / iPadOS / macOS POS | **NOT VERIFIED** |
| Backup | **PASS** (logical) |
| Restore | **PASS** (logical CI drill) / prod restore **NOT RUN** |
| PITR | **NOT RUN** (runbook only) |
| Load Test | **NOT RUN** (baseline docs only) |
| Internal Security | **PASS** |
| External Penetration Test | **NOT EXECUTED** |
| Production Deployment | **NOT READY** |
| Paid Billing | **DEFERRED** (entitlements live; gateway not integrated) |
| Documentation | **CURRENT** with drift marks on obsolete tenancy claims |
| **Go-Live** | **NOT READY** |

---

## What this phase completed (code)

1. **Default Main Store** on tenant seed (entitlement-aware via `create_store`)  
2. **UserStoreMembership** model + migration `20260917_0105`  
3. **Store RBAC** — `GET/PUT /users/{id}/stores`; POS store list + open session enforce membership  
4. **Docs honesty** — SUPERSEDED markers for database-per-tenant claims  
5. **Auth gate / store parity** (prior commits on this branch)  
6. **Offline POS foundation** — IndexedDB queue + 7-day auth envelope (`frontend/lib/posOffline.ts`), SW shell cache (`public/sw.js`), POS cash-only offline checkout + auto-flush, `client_request_id` idempotency (migration `20260917_0106`)  
7. **Offline recovery package** — export/import pending queue JSON (no tokens) from POS UI  
8. **POS device heartbeat** — `pos_devices` table (migration `20260917_0107`), `POST /pos/devices/heartbeat`, `GET /pos/devices`  
9. **OS lockdown guide** — `docs/POS_DEVICE_LOCKDOWN_GUIDE.md` (guidance only; hardware NOT VERIFIED)  
10. **This checklist + report**

---

## Exact remaining blockers

### BLOCKER 1 — Production not deployed
- **Why:** No live HTTPS tenant endpoint proven from this environment  
- **Work:** Deploy RC to VPS; env secrets; migrations; workers; health checks  
- **Test:** `/health/ready` 200; login; one POS sale  
- **Automation:** Can prepare compose/K8s; **cannot** operate your VPS alone without credentials  
- **Owner:** Required

### BLOCKER 2 — Offline POS endurance / marketing claims
- **Why:** Code foundation + recovery export + heartbeat are PARTIAL; physical 7-day endurance, multi-device reconnect certification, and alert dashboard are NOT RUN / absent  
- **Work:** Device certification + alert UX + OS lockdown OR remove offline claims from sales materials  
- **Test:** Physical offline 50+ sales + reconnect idempotency + 7-day window + recovery restore drill  
- **Automation:** Foundation + recovery JSON + heartbeat API shipped; remaining is certification + ops UX  
- **Owner:** Product decision + physical tests

### BLOCKER 3 — Physical device / platform certification
- **Why:** No Windows/Android/iPad/macOS verification evidence  
- **Work:** Run §51–§53 device tests  
- **Automation:** Cannot  
- **Owner:** Required

### BLOCKER 4 — Staging restore + load + pen test
- **Why:** Operational proof missing  
- **Work:** Execute DR restore drill, load suite, schedule external pen test  
- **Automation:** Scripts/docs only  
- **Owner / external:** Required

### BLOCKER 5 — Multi-company (only if sold as multi-company SaaS)
- **Why:** Tenant has one company profile today  
- **Work:** New Company entity under Tenant + switcher + isolation — large redesign  
- **Automation:** Possible as dedicated epic  
- **Owner:** Scope decision — **NOT required** if you sell one-company-per-tenant MVP

---

## ACTION REQUIRED FROM OWNER

1. Deploy release candidate to staging/production VPS.  
2. Configure production domain / HTTPS / secrets / SMTP.  
3. Run DB migrations including `20260917_0105`, `20260917_0106`, and `20260917_0107`.  
4. Decide: **defer offline marketing** OR fund endurance/device-alert epic before launch (foundation + recovery + heartbeat already in code).  
5. Connect physical Windows POS; run online sale + (if claiming offline) offline protocol + recovery export drill.  
6. Connect Android tablet; repeat.  
7. Perform staging restore drill; record RPO/RTO.  
8. Execute load test against staging.  
9. Arrange external penetration test.  
10. Review this report and `docs/GO_LIVE_CHECKLIST.md`; sign go-live only when blockers cleared.

---

## Recommended commercial MVP positioning (honest)

**Ship now as:** Multi-tenant online ERP — inventory, purchasing, sales, POS, accounting, tax, credit, multi-store entitlements, store membership RBAC, platform-assigned subscriptions.

**Do not claim yet:** Certified 7-day offline POS endurance, multi-company under one login, paid self-serve checkout, platform pen-test complete, hardware universal compatibility, device alert/MDM lockdown.
