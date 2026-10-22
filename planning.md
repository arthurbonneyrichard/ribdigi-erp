# Implementation plan

Entry point only. Status language in `docs/COMMERCIAL_READINESS_REPORT.md` and `docs/OFFLINE_POS.md` stays authoritative. This file does not recertify anything.

## Objective and scope

Ship a retail ERP that isolates each company, enforces plan and role limits on the server, posts balanced sales, and lets a prepared till queue supported POS sales. Hotel and restaurant are separate industries. Pharmacy remains only for an existing pharmacy company.

In scope: the running FastAPI and Next.js app on branch `production`. Out of scope unless a later decision says otherwise: schema-per-tenant, a live payment gateway, Offline Complete, FMCG restoration, and production deployment.

## Current architecture and verified baseline

Inspected on this tree (HEAD `d41426f99e`, branch `production`). Later cashier, offline, and company-format edits were uncommitted and were not treated as a release.

- Shared-schema `tenant_id` (`docs/ADR_001_TENANCY.md`). Alembic is a single head, `20261022_0142` (hybrid extra NOT NULL defaults; after storefront media `20261021_0141`). Do not apply it to live `ribdigi_erp` from this plan.
- Industries a new company can choose: retail, hotel, restaurant. Sidebar industry group is hotel and restaurant only. Pharmacy is absent from `Shell.tsx`.
- Store entitlements count active stores and do not delete stores on downgrade (`backend/app/store_entitlements.py`).
- POS offline queue flushes to `POST /pos/sales` with `client_request_id`. Policy field `offline_complete_claimed` is false (`backend/app/offline_pos.py`).
- Recorded bank tenders, including Mobile Money, use GL 1010 (`backend/app/accounting.py`). Gift card and loyalty ignore a cash account id and debit 2150 and 2160. A non-cash tender that resolves to till cash 1000 is rejected. Subscription billing is a separate mock-or-unconfigured gateway (`docs/SAAS_BILLING.md`).
- Cashier presence is mounted on User Management (`frontend/app/(dashboard)/users/page.tsx`). The company dashboard page does not import `CashierPresencePanel`.
- Brand `#4AB012` is the `--brand` token in `frontend/app/globals.css`.

**2026-10-14 review.** `docs/COMMERCIAL_READINESS_REPORT.md` now leads with that day’s addendum: not a general release, not certified. The 2026-10-13 addendum and the 2026-10-05 **Not ready for market** section stay. Offline Complete remains missing (`docs/OFFLINE_POS.md`). `offline_complete_claimed` stays false.

**2026-10-14 later pass.** In-memory tests now cover gift-card and loyalty issue, redemption, refund, and reversal, split tenders, and rejected account ids. A lost POS response with the same `client_request_id` posts one sale. Security suites that were run passed. Security stays Blocked. Retail, hotel, and restaurant stay Not ready. Offline POS stays Incomplete. No authorized `.ribbak` was found, so no disposable restore was created.

**2026-10-14 evening.** Decisions are unchanged: Security Blocked, Retail Not ready, Offline POS Incomplete, Hotel Not ready, Restaurant Not ready. Previously unexecuted auth, permission, isolation, 2FA, upload, and hotel cross-tenant tests passed after the login page was pointed back at `unreachableApiMessage('/auth/login')`. `npm run test:offline` passed 20. Payment routing now also rejects an inactive `1010` or `2160` and keeps Mobile Money and bank transfer out of drawer cash. No authorized backup file exists, so no disposable database was created. The local site is the login form, so signed-in walkthroughs were not run. `offline_complete_claimed` stays false. Sale replay in `api.py` was not edited in this pass.

**15 October 2026 UTC.** Statuses stay Security Blocked, Retail Not ready, Offline POS Incomplete, Hotel Not ready, Restaurant Not ready. Supplier payments now require `credit:read`, so a cashier `POST` returns 403 (`tests/test_cashier_pos_only.py`, 4 passed). `npm run test:offline` passed 21, including one replay after IndexedDB is closed. A local PostgreSQL 16.14 dump of `ribdigi_erp` restored into `ribdigi_drill_20261015`, matched user, sale, and journal counts with no tenant mix, and was dropped. That is not a production restore. The signed-in receipt-to-report walkthrough was not run. `offline_complete_claimed` stays false.

**15 October 2026 UTC, later.** A signed billing webhook now requires the company, the amount, and the currency. Leaving any of those off does not mark an invoice paid and does not save a reusable authorization. Checkout and charge send the company id in provider metadata. Cashier presence for a manager with store membership lists only those stores. A manager with no membership, and a company admin, still see the company's cashiers. `tests/test_saas_billing_r1.py`, `tests/test_cashier_presence.py`, and `tests/test_billing_gateways.py`: 23 passed.

**15 October 2026 UTC, security.** The staff list follows the same store membership rule. A manager assigned to one store does not see people assigned only to another store, and cannot open that record or filter the directory by the other store. The named auth, isolation, 2FA, upload, billing, and presence files passed: **123 passed** in 285.97s. Security is **Ready**. It is not Verified.

**15 October 2026 UTC, retail.** `tests/test_retail_pos_arithmetic_fixture.py` passed **1** in 6.25s. That sale reconciles the receipt, stock, cash tender, journal, replay, and daily sales report on the disposable test company. Retail is **Ready**. Offline POS stays Incomplete. Hotel and restaurant stay Not ready. Unsigned `/security` and `/pos` returned to the login form. Nobody signed in through the browser. `ribdigi_erp` was not written.

**15 October 2026 UTC, release.** The current status is a **general release**. It is **not certified**. It is **not Offline Complete**. `offline_complete_claimed` stays false. The 2026-10-05 “Not ready for market” paragraph stays as history.

**15 October 2026 UTC, offline.** Offline POS is **Ready**. `frontend` `npm run test:offline` passed **21**, including prepare, a queued cash sale, a closed browser database, and one replay of the same `client_request_id`. That is not Offline Complete. `offline_complete_claimed` stays false.

## Feature gaps and defects

| Priority | Item | State |
| --- | --- | --- |
| P0 | Cross-tenant reads or writes, duplicated `client_request_id` sales, stock or journal drift | In-memory replay tests passed 2026-10-14. A different body on a used id is HTTP 409. The full suite and a signed-in till were not re-run. |
| P1 | Offline Complete | Missing. Device id is not strong binding. A private window with no till-agent journal cannot recover sales. Upload needs the POS page open and signed in. No live site test. |
| P1 | Signed-in single-store and multi-store browser walkthrough | Not run. |
| P1 | Company date and number format on screens the cashier can open | Implemented. `GET /me` returns the tenant format. Saving the company profile clears the in-memory snapshot so open screens reload it. `tests/test_formatting_f1.py` passed 3 tests in 4.65s on 2026-10-14. The format-cache unit test passed inside `npm run test:offline` (18 passed). A signed-in browser save was not clicked. |
| P1 | Subscription paid state | Signed webhook only. No live charge in this tree. |
| P0 | Gift-card or loyalty tender debiting till cash when a cash account id is sent | Fixed in this working tree. The payment routing file’s 9 tests passed inside the 2026-10-14 combined run (the two failures were replay tests, later fixed). A refund of those tenders credits 2150 or 2160. The plastic card balance is not restored, because a return has no card code. |
| P2 | Staff-guide PDF contents, dashboard headline versus ledger, gift-card redemption on a signed-in till | Staff guide text is verified by `test_staff_guide_follows_industry_and_role` (1 passed, 0.87s). Dashboard purchases test passed 2026-10-14. Gift-card redemption on a signed-in till was not clicked. |

## Dependencies and unresolved decisions

- Schema-per-tenant remains post-MVP (`docs/ADR_001_TENANCY.md`). Do not start it in this plan.
- Live Paystack, Flutterwave, or another gateway stays off until secrets exist only in the server environment and a signed webhook is proven. Do not add secrets to the repo.
- Offline Complete is not a documentation flip. It needs strong device binding, queue recovery after cleared storage, and a live-site test. None of those are decided as in-scope work here.
- Empty store memberships still see all tenant stores (grandfathered). Assigned memberships constrain access.
- Production HTTPS, workers, load certification, and physical POS checks remain owner tasks in the commercial report.

## Ordered phases

1. **P0 — protect money and isolation.** Keep tenant filters, idempotent sales, and balanced stock journals. Do not change posted amounts during sync.
2. **P1 — core workflows that are still wrong.** Role and plan gates, store caps, POS shifts and receipts, offline prepare / queue / sync / conflicts, subscription webhook matching, company format visible to every signed-in role.
3. **P2 — usability and evidence.** Aria labels already in progress via `AGENTS.md`, personal theme, performance, secondary reports. Do not mark a module done because one screen loads.

## Migrations

`20261022_0142` relaxes extra NOT NULL columns a different checkout added on the local Docker DB (`SET DEFAULT` / `DROP NOT NULL` if present; add `sales_invoices.credit_limit_overridden` only because this tree now maps it). Apply to local Docker only. Future schema changes go through Alembic `upgrade head` against a confirmed disposable database only. The live app database name `ribdigi_erp` on `127.0.0.1` is not a migration target in this plan.

## Offline prepare, auth, queue, and sync

Implemented behavior to preserve:

- Prepare only after online sign-in. Unprepared and expired copy is in `rule.md`.
- Grant is device + company + user and expires (`offline_auth_hours`, default 168, tenant override 1–168).
- Queue is encrypted IndexedDB partitioned by tenant, user, and store.
- While the till is open and signed in, sync is automatic. The cashier does not press Send.
- 5xx, 429, 408, and network errors stay pending and retry. 4xx conflicts (price, stock, credit) stay for a manager. Credit conflicts are not auto-posted.
- A closed browser cannot upload. `localStorage` is not the device binding. The till-agent journal on this PC is the copy that can survive cleared site data. A private window with no journal file cannot recover the sale.

## Security and financial verification

- Isolation tests and store-cap tests are the regression set when those modules change.
- A POS sale check is: one sale, one `client_request_id`, stock movement, balanced journal, tender on the correct GL, shift totals unchanged except for that sale.
- Subscription: browser return leaves the invoice unpaid. Only a signed webhook with the company, amount, and currency all present and matching may mark it paid or save a reusable authorization. A missing field is not a match.
- Cashier presence follows store membership. No membership still means every store in that company.
- No password reset, no drill-cashier sign-in, no closing `SHIFT-2026-0001` or `SHIFT-2026-0002` as part of doc or format work.

## Browser walkthroughs still required

Not done: sign in as company admin and as cashier on a local retail company; confirm single-store hides store network UI and multi-store asks for a store before the shift; save a company date format and see it on POS without a full reload; confirm cashier presence on User Management and not on the company dashboard. Do not type the drill password into a committed script.

## Backup and restore

Follow `docs/DR_LOGICAL_BACKUP_RUNBOOK.md`. The 2026-10-13 local copy restore into `ribdigi_restore_drill` is recorded and was dropped. It was not a production backup. On 15 October 2026 UTC, `pg_dump` and `pg_restore` PostgreSQL 16.14 inside `ribdigi-erp-postgres-1` copied local `ribdigi_erp` into disposable database `ribdigi_drill_20261015`. Counts matched and tenant-mix checks were zero. That database and the dump file were removed. `ribdigi_erp` was not overwritten. No `.ribbak` restore was run. Do not restore over `ribdigi_erp`.

## Acceptance and release blockers

**21 October 2026 UTC, ecommerce.** Retail trial/professional/enterprise can enable a built-in storefront and a WooCommerce connector on a verified tenant domain. Starter and hotel/restaurant stay gated. Live DNS, TLS certificates, and live processor secrets stay owner tasks. Offline Complete stays missing.

**21 October 2026 UTC, ecommerce verification.** In-memory ecommerce + jobs OpenAPI/Celery suites passed. Frontend typecheck and production build include `/ecommerce` and `/storefront`. A disposable-company preview is the only ready path. Public pilot stays BLOCKED on owner DNS, TLS, and a tenant webhook. `ribdigi_erp` was not migrated.

**21 October 2026 UTC, ecommerce completion.** Remaining in-repo gaps closed: owner health without secrets, domain re-verify on TXT loss, catalog search/category/pagination, packed/dispatched/delivered, posted-invoice return/refund, forged webhook and duplicate Woo order tests. Still BLOCKED: live DNS, TLS certificates, live processor secrets, public hostname pilot. Offline Complete stays missing.

**21 October 2026 UTC, ecommerce shoppers / variants / Woo outbound.** In-repo PARTIALs closed: storefront shopper accounts (not ERP users), variant cart/order/reservation lines, best-effort Woo PUT for `woo:{id}` order status and stock. Still BLOCKED: live DNS, TLS certificates, live processor secrets, public hostname pilot. Offline Complete stays missing.

**21 October 2026 UTC, website linking.** Domain create accepts a hostname or https website URL, can link the company website, and can unlink. WooCommerce connector save/disconnect is on the Online store desk. Reserved Ribdigi hosts stay rejected. Live DNS, TLS, and live processor secrets stay owner tasks.

**21 October 2026 UTC, Online store desk.** Staff `/ecommerce` is organized into storefront, website/domains, catalog, orders, payments, and Woo connector cards using the shared desk tokens. Shopper `/storefront` chrome uses the same brand variables but stays on `sf-*` classes. Checkout and payment rules were not rewritten.

**21 October 2026 UTC, Online store Settings nav.** Online store left Sales and POS and now sits in Settings next to Company, Security, Printers, and Integrations. `/ecommerce` is unchanged. Retail + package gate stays. Hotel and restaurant still do not see it unless entitled. Desk status, website link/unlink, copy TXT, reserved-host copy, and Woo connect/disconnect were tightened on the same page. Checkout, payments, reservations, POS posting, and the offline queue were not rewritten. `offline_complete_claimed` stays false.

**21 October 2026 UTC, storefront shopper UI.** Public `/storefront` now uses shared forest/brand chrome, hero, product page, cart qty/remove, empty/error states, and honest payment copy. Staff `/ecommerce` gained a package-denied empty state, warehouse hint, catalog search, and HTTPS-ready honesty. Checkout and reservation rules were not rewritten. Live DNS/TLS/gateway stay BLOCKED. `offline_complete_claimed` stays false.

**21 October 2026 UTC, storefront media.** Settings `/ecommerce` uploads a storefront logo, banner, and favicon (separate from the ERP sidebar logo). Public shop shows them via `/storefront/media/*` and published product images via `/storefront/products/{id}/image`. Empty until uploaded. Migration `20261021_0141` is in-repo only — not applied to live `ribdigi_erp`. Live DNS/TLS/gateway stay BLOCKED. `offline_complete_claimed` stays false.

**22 October 2026 UTC, hybrid schema.** Local Docker Postgres was migrated by another checkout that added NOT NULL columns this tree does not fill. `20261022_0142` sets defaults or drops NOT NULL when those columns exist, and maps `sales_invoices.credit_limit_overridden`. Apply on local Docker only. Live `ribdigi_erp` / Dokploy stay unmigrated. `offline_complete_claimed` stays false.

**22 October 2026 UTC, retail launch checklist.** Owner file `Ribdigi Retail Launch Checklist.md` is a stub; the full 22-item bar is in the sibling HTML export. In-repo bugs closed this pass: one warehouse per store + POS pick-one, dashboard company-wide expenses, owner title contrast, sales path spacing, phone sidebar padding, credit party clear, retail batch-holds skip, shop ticket close, legal pages on login, skip till-agent 8765 unless set, hide AI chat when off. Test import + stale head/COA/`available_qty` repaired; ~42 redesign UI-text tests still open. Still BLOCKED: commit/deploy, live Dokploy migrate, SMTP, live billing, production secrets, SMS, signed-in walk, Offline Complete. `offline_complete_claimed` stays false.

**22 October 2026 UTC, launch tests.** Redesign screen-text tests now read the current desks (`RowActions` `ariaLabel`, path steps, POS Charge/Print, warehouse low-stock empty copy). Ops evidence writes to `/opt/ribdigi` when possible and otherwise a temp file; disposable Alembic skips only when local Postgres is missing or cannot create `ribdigi_alembic_head_verify` (does not swallow assertion failures). Still BLOCKED: commit/deploy, live Dokploy migrate, SMTP, live billing, production secrets, SMS, signed-in walk, Offline Complete. `offline_complete_claimed` stays false.

**21 October 2026 UTC, dashboard clock.** The company dashboard greeting clock digits are 3rem (was 2rem after desk compact). POS has no header clock. Greeting copy, cart, and catalog sizes were not changed. Signed-in walkthrough was not run. Offline Complete stays missing.

**21 October 2026 UTC, POS layout.** The till workspace is cart-left / catalog-right, with category chips, a compact keypad, and a last-receipt preview after Pay. Sale posting, tenders, and the offline queue were not rewritten. Signed-in walkthrough was not run. Offline Complete stays missing.

**21 October 2026 UTC, ERP desk language.** Shared spacing tokens, PageHeader, and EmptyState were applied so tenant desks match the compact POS reference. Remaining tenant and platform desk titles now use PageHeader. Page-level empty panels on ecommerce, customers, credit, reports, and inventory use EmptyState. Table-cell empty rows stay in place. Dashboard decorative sun/cloud is hidden. Sidebar collapse chevron is unchanged. POS till chrome, login, and storefront stay on their own layouts. Business rules, payments, and Offline Complete were not rewritten.

Acceptance for a task is the evidence in `tasks.md` (command and outcome, or file inspection). Release blockers that remain:

- Offline Complete is missing. Do not claim it, and do not set `offline_complete_claimed`.
- General release. Not certified. Not Offline Complete. The 15 October 2026 UTC note is the latest result. Security is Ready and not Verified. Retail is Ready on the disposable sale. Offline POS is Ready. Hotel and restaurant stay Not ready. `offline_complete_claimed` stays false. The 2026-10-05 “Not ready for market” paragraph stays as history.
- No verified live site. No production deploy from this plan.
- Signed-in retail walkthrough beyond the one recorded local offline sale is still open. Hotel and restaurant were not signed in separately.
- A gift-card refund credits liability 2150 and does not restore the card balance.
- A quote retry that omits `unit_price` matches the stored quote even when the first request sent a price. No migration was added to store a quote fingerprint.
