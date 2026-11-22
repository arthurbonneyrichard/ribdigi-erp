# Gym desk

A gym is its own industry on `gym_*` tables, with its own member list and till. It never writes to retail sales, customers or `pos_sessions`.

## Sidebar

A gym gets its own sidebar (`GYM_NAV_GROUPS`): Dashboard; Front desk (Door, Members, Classes, Gym floor); Plans and money (Plans, Reports); Staff; Notifications; Help; Settings. No retail menus and no in-page tab strip.

## Screens (`/gym`)

- **Today:** active members, visits, classes, money taken, who ends this week.
- **Door:** find a member, let them in or see plainly why not. Refusals are recorded.
- **Members:** the till, add members, sell, renew, freeze, cancel.
- **Classes:** times, trainers, places, bookings, who came.
- **Gym floor:** personal training sessions (a trainer can never hold two overlapping live sessions), lockers (one per member, active members only), equipment with fault tickets (a machine is Working only when no fault is open; retiring is final), and guests (in/out, host must be active).
- **Fitness:** exercise library, workout programmes per member (days, sets, reps, weight), a once-a-day workout log per exercise, and body measurements with BMI and change since the first record. Trainers and managers only; the front desk is refused (`fitness` area). Tracking only, not medical advice. **Nutrition** (same screen and access): one live plan per member with calorie/protein/carb/fat/water targets, allergies, preferences and meals, plus one intake log per day.
- **Plans:** price, days, visit limit. A day pass is a one-day plan.
- **Reports:** money taken, plans sold, renewals, new members, visits, who ends soon.

## Rules

- Selling needs an open till. Every movement of money is a row in `gym_payments`.
- A plan is booked as revenue on the day it is sold. It is not spread over the months it covers.
- A renewal starts the day after the current plan ends, so no days are lost.
- A member counts one visit a day. A visit-limited plan stops at its limit.
- Freezing blocks the door. Unfreezing adds the frozen days back, up to 180.
- A new plan price applies to the next sale. Members keep what they paid.
- Cancelling can refund up to what was paid, and reverses the sale and tax in proportion.
- Class booking needs an active membership and a free place. A full class takes a waiting list; when a booked place is cancelled the oldest waiting member whose plan is still active is promoted automatically.

## Staff jobs

`gym.job` limits each role inside `require_permission("gym", …)`, and `GYM_ROLE_HREFS` in `frontend/lib/tenantNav.ts` mirrors it for menus.

| Role | Can do |
| --- | --- |
| Gym Manager, company admin | everything, including plans, refunds and reports |
| Front Desk | members, selling, the till, the door, classes |
| Trainer | the door, classes, training sessions and fitness (programmes, measurements); sees no money, lockers, guests or equipment |

## Demo

`PYTHONPATH=. python scripts/seed_gym_demo.py` creates `demo-gym-rec` (Iron Peak Fitness; owner, front desk and trainer logins). It refuses to run in production.

## Stage 2 (19 Nov 2026)

Each part has its own migration (`20261119_0192` to `0200`), service, routes and tests.

- **Classes repeat weekly** (`repeat_weeks` 1 to 52). A series shares `series_id`; `POST /gym/classes/{id}/cancel?series=true` cancels that class and every later one in the series, never past ones.
- **Per-plan door rules** (`POST /gym/plans/{id}/access`): opening and closing time (a window may cross midnight), allowed days (1 Monday to 7 Sunday) and branch scope (`all` or `home`). Read in the company's own timezone. The rules only ever add a refusal after the membership checks.
- **Branches** (`gym_branches`): optional. A member has a home branch; a door scan may name the branch it is at. A `home` plan refuses other branches. A closed branch refuses scans. Report: `GET /gym/reports/branches`.
- **Door credentials**: QR, card, RFID, NFC, barcode. Only a SHA-256 hash is stored; a generated token is shown once. A card number is unique across the whole system. Revoking stops it at once. `POST /gym/check-ins/scan` takes a code.
- **QR images** are drawn on the server (the existing `qrcode` package) and returned as `qr_png` when a code is issued and in the member portal's door code.
- **Guest and locker fees** go through the gym till (`gym_fees.py`): a guest's entry fee (`fee` + `method` on `POST /gym/guests`) and a locker rental (`rental_days`, `fee`, `method` on assign; `POST /gym/lockers/{id}/renew`). They need an open till, are booked as revenue the day they are taken (net to 4000, tax to 2100) and are rows in `gym_payments` (`guest_fee`, `locker_fee`) so the till count includes cash fees. A renewal starts the day after the rental ends, or today if it already ended; an ended rental shows `overdue`. Fees cannot be refunded in the app yet.
- **Member files** (`gym_member_files`): photo (one; a new one replaces it), ID, signed waiver and progress photos, uploaded as image or PDF into tenant media storage and checked for real type and size. Photo, ID and waiver are front-desk records; progress photos need the `fitness` area, so the front desk never sees them and a trainer never sees IDs. The member portal never serves files.
- **Printable membership card** (`POST /gym/members/{id}/card`): an HTML page with photo, plan and a QR, to print or save as PDF. Printing issues a new `card` credential and cancels the previous printed card, so a lost card stops working.
- **Facilities** (`gym_facilities`, screen Setup > Facilities): sauna, pool, studio, court. A booking must sit inside opening hours (company local time), in the future, within the facility's longest booking, for a member with an active membership, never overlap that member's other bookings, and never exceed the places at any moment (the facility row is locked while booking). A member can book and cancel only their own slots from the portal.
- **Trainer commissions** (`gym_commissions`, screen Setup > Trainer pay): a manager sets a percent per trainer. Completing a session accrues that percent of the trainer's listed session price, once per session (a cancelled or no-show session earns nothing). The listed price is used whether or not the session was charged at the till. This is a record for payroll, not payroll: `POST /gym/commissions/pay` marks a period paid with a reference and does not post to the books or the HRM, so no pay is counted twice. A trainer sees their own owed total in My work.
- **Gym shop** (`/gym/shop/*`, `gym_products`, `gym_shop_sales`): the gym's own products and stock, separate from the retail catalogue. A sale needs an open till and books Dr money / Cr revenue 4000 / Cr tax 2100 plus Dr 5000 cost of sales / Cr 1200 inventory at the average cost, and cannot take stock below zero. A restock is paid from the till (negative `gym_payments` row, Dr 1200 / Cr money) and updates the average cost. Selling is front desk and manager (`desk`); products, prices and restocking are manager only. A **refund** (manager only) returns stock at the cost it was sold at, reverses revenue, tax and cost of sales in proportion, pays the customer from the till and can never exceed what was sold. **Stock on credit** (`method=credit` with the supplier's name) books Dr 1200 / Cr 2000 and makes a supplier bill; no till is needed until the bill is paid from the till (Dr 2000 / Cr money). Screen: **Shop** (Sell, Products and stock, Sales and refunds, Supplier bills).
- **Equipment assets** (`POST /gym/equipment/{id}/asset`, `GET /gym/reports/equipment-assets`): purchase date, cost, supplier, warranty and useful life. Book value is straight-line by full months, computed on the day you ask and never below zero; retired equipment is left out of the totals. It is a report only: nothing is posted to the ledger. No screen yet (API only).
- **Devices** (`gym_devices`): a reader or turnstile is registered as `verified=false` and shows "not yet tested on real hardware" until a manager marks it tested. Nothing in the code claims a device works.
- **Offline door sync** (`POST /gym/door/sync`): a device keeps its own `event_id` per scan, so a retry never counts twice. A scan older than 24 hours, dated in the future, from an unknown code or refused by the membership is recorded and flagged under "Scans to check" instead of becoming a visit. `GET /gym/door/roster` gives hashes of active members only, for a reader to cache. Offline entry is therefore decided by what the device cached plus a check when it syncs; it is not unrestricted.
- **Leads and campaigns** (`gym_leads`, `gym_campaigns`): follow-ups due, trial days, conversion to member (the first plan is still sold at the till), conversion and trial reports by source. Offers go only to members or leads who agreed (`marketing_consent`) and never to an address on the platform's marketing suppression list; email carries the signed unsubscribe link. The only message that skips consent is a renewal reminder (`kind=service`, audience `expiring`). Sending uses the company's own SMS and SMTP settings; the result records `sent`, `failed` or `skipped` per person and a retry sends only the failed ones. WhatsApp is not connected.
- **Member portal** (`/gym-member?t=...`, API `/public/gym-member/*`): staff make a private link (`POST /gym/members/{id}/portal-link`); only a hash is stored, it expires in at most 30 days and a new link cancels the last. The member id always comes from the token. A member sees their plan, books and cancels classes (never sees other members' names), sees their programmes, measurements and nutrition plan, logs their own workouts and intake, sees payments, gets a rotating door code, sends feedback and sets marketing consent. **Renewing by paying is not here**: Ribdigi records payments but does not take them, so renewals stay at the till.
- **Trainer portal** (`/gym/trainer-portal/*`, screen **My work**): a manager links a trainer to a staff login (`POST /gym/trainers/{id}/link-user`). The trainer then sees only their own sessions, programmes and assigned members (through a session or an active programme), and can record measurements for those members only.
- **Member feedback** (`gym_feedback`): complaint, comment or 1 to 5 trainer rating; managers close it with a note; `GET /gym/reports/trainer-ratings`.
- **Insights** (`/gym/insights/*`): churn risk with reasons and a suggested next step, attendance trends, repeat equipment faults, a 30-day summary and draft workout plans. **These are fixed rules on your own records, not a language model** (the platform has no LLM client wired); every response says `method: "rules"`. A manager can switch them off. A workout draft is built from the gym's own exercise library, is not saved, and needs a trainer's review. Nothing is sent to an outside service.

New areas for `gym.job`: `fitness` (trainer and manager only; the front desk is refused). Leads, credentials, portal links and consent use the front desk's `members` area; branches, devices, plan door rules, campaigns, feedback, reports and insights are manager only (`correct`).

## Not built yet

- Real hardware: no reader, RFID/NFC, fingerprint, face or turnstile has been connected or tested. Devices stay `not yet tested on real hardware`.
- WhatsApp and push messages, and timed (scheduled) campaigns other than the daily renewal reminder. Reminders exist as a button (`POST /gym/reminders/run`, once per channel per day, `kind=service`). A Celery job `send_gym_renewal_reminders` (07:10 daily) runs them for gyms that switched it on (Growth > automatic renewal reminders: off, SMS, email or both; **off by default**). Restart the Celery worker and beat after pulling.
- A language-model assistant (chat, drafted nutrition plans, written reports). Nutrition drafts were left out on purpose: they need age, sex and activity, which the gym does not collect.
- Paying or renewing from the member portal (needs a verified payment gateway).
- A screen for equipment assets and posting depreciation to the ledger, linking the gym shop to the retail POS (the gym desk is deliberately isolated from it), per-branch shop stock, multi-branch revenue beyond the visits report, and handing commissions to the HRM payroll automatically.
