# Hotel production readiness

**Date:** 5 November 2026 UTC.

**Verdict: Ready for a supervised first hotel once this work passes CI and is promoted to `production`. Not yet ready to sell widely.** The money and staff-access blockers below are fixed and tested. What remains is real-world use, the known limits listed here, and the same two owner actions as retail and restaurant (external penetration test, production restore drill).

Hotel is its own desk, isolated from retail and restaurant. The back office (accounting, tax, purchasing, supplies) is the shared engine, kept per company by `tenant_id`.

## What the audit found and fixed

| Finding | Before | Now | Evidence |
| --- | --- | --- | --- |
| Hotel income never reached the books | A paid GH₵1,600 stay left the trial balance empty and P&L revenue at 0 | Charges and payments post journals; voids reverse them; moved charges keep theirs | `tests/test_hotel_folio_books.py`; live stay: cash 1,600, revenue 1,393.33, tax 206.67 |
| Tax setting did nothing | Rooms untaxed at any tax %, invoice tax hard-coded to 0 | Tax % applies to rooms, extensions and early, late and no-show fees; shows on the bill, invoice, tax report | same; new setting **My room rates already include tax** (on by default, so quoted prices do not change) |
| Payments could not be corrected | No refund; a mistyped payment was stuck; a guest's credit vanished at checkout | Refund from the bill, full or part, never more than was paid; checkout is blocked while the guest is in credit | same |
| On-account stays showed as paid | Invoice marked paid, nothing left to collect | Stays owed on Guest invoices until money comes in | same |
| Weekend rate overcharged | One Saturday night put the whole stay on the weekend rate | Each night at its own rate, blended into the nightly figure, on the desk and the booking page | same |
| Every hotel role could do everything | A housekeeper could take payments, add charges, change settings, read reports | `hotel_jobs.py` gives each role its job on the server; menus and direct addresses follow | same; live API and browser walk per role |
| Float close could not catch a shortfall | Total of all payment types, no expected cash | Cash taken, what should be in the drawer, and over or short on close | same |
| Lists said "No tasks" while loading | Empty messages during a two-step load | Everything loads at once; "Loading…" until it arrives | browser walk |

## Made easy to use, feature by feature

| Feature | What changed |
| --- | --- |
| Dashboard | Today comes first: arriving, leaving, in house and free tonight tiles open the work. **Needs attention** lists what is waiting, **Quick actions** follow the signed-in role, then charged, paid and owed, then the room board. Charts sit under **More numbers**. Rooms waiting for housekeeping no longer count rooms with guests in them, the amount owed shows its currency, and a desk left open overnight moves to the new day. |
| Reports | Five views: Overview, Rooms, Income, Money owed, Supplies. Today, Last 7 days, This month and Last month. Changes against the same number of days before, occupancy and revenue by day, what is booked ahead, income per room and room type, stays by source, how guests paid, extras without room charges, tax charged, and who owes. Download CSV and Print. |
| Dark mode | Every hotel screen was measured for text contrast and bright panels: 56 problems, now none on the last full check. Shared dialogs had no dark styling and showed white text on white; that fix is in `globals.css` and helps every desk. |
| Guest documents | The bill and confirmation print with the hotel name, address and tax number, and can be emailed to the guest once company email is set up. |
| Late list | Front desk shows guests who should have left and arrivals who did not come, with Extend and No-show on the row. The dashboard flags them. |
| Help | Every hotel feature has **How this works**: what it is for and the steps in order (`lib/hotelGuides.ts`). It opens at first and stays closed once hidden. The dashboard shows a normal day from morning to night audit. |
| Reservations | One screen at a time: **Stays**, **Calendar**, **Book a stay**, **Group stay**, **Online booking**. The list comes first and can be searched. |
| Book a stay | Three steps. Free rooms follow the dates, the price comes from the server (`GET /hotel/quote`), the guest is found by typing, and extras sit under More options. |
| Stay changes | Extend, change room, duplicate and the new **Edit stay** each open their own small window. Change room lists only rooms free for that stay. |
| Check in | Warns before checking in early or into a room still needing cleaning. A future stay shows Check in early under the menu. |
| Check out | With money owing it offers **Take payment first** or **Check out and leave the balance**. |
| Room board | An arriving guest offers Check in, a dirty room offers Housekeeping or booking from tomorrow, a closed room offers Maintenance. |
| Guest bill | Payment comes first with the amount owed filled in. Check out, print and close sit at the top. Service list now loads on Guest bills and Front desk. Void and refund use proper windows and are hidden from staff who cannot do them. A closed bill stops offering charges. |
| Rooms | Rooms can be edited and taken off sale, then put back. Rate plans have their own view and can be edited and turned off. |
| Guests | Search, Edit, and Details with stays, balance and merge. |
| Housekeeping, Maintenance | To do and Done lists, **Mark clean**, **Mark fixed**. Lost and found has its own view and items can be closed. |
| Restaurant and bar | Pick the guest by room, tap the menu item, post to the bill. One-off items sit under a fold. |
| Cash and night audit | Shows only the next action: open the float, or count and close it. Closed floats show over or short in a table. |
| Reports, Settings, Events, Supplies | Last 7 days and This month, plain names for ADR and RevPAR, settings grouped with a warning when tax is 0, a confirm before cancelling an event, a line under each supplies link. |

Fixes found on the way: a room being cleaned today could not be booked for next week; retrying a failed booking added the new guest twice; tapping an arriving guest on the board gave a "No bill yet" error; bills said "1 night(s)"; lost items could never be closed. Each screen now asks the server only for what it shows, because moving quickly between tabs could reach the rate limit.

## Screens

Each tab has its own title. Reservation rows show one main action, with the rest under a menu. Lists come first, with forms behind an Add button. **Front desk** has arriving, leaving and in-house tiles, and a **room board** by floor: tap a guest to open the bill, tap an empty room to book it. The **guest bill** shows charges, tax, paid and still to pay. The cash screen shows what should be in the drawer. Brand greens throughout; amber and red only mark status.

## Checks run

| Gate | Status | Evidence |
| --- | --- | --- |
| Hotel books, tax, refunds, roles, float, rates | pass | `tests/test_hotel_folio_books.py` |
| Signed-in walk, desktop | pass | Every hotel tab, no failed calls (demo company `demo-hotel-rec`, `scripts/seed_hotel_demo.py`) |
| Phone width 390 px | pass | 17 hotel screens, no sideways scroll, no junk text, no errors |
| Staff roles | pass | Housekeeping, front desk and cashier signed in: right home, right menu, refused elsewhere |
| Desks closed to each other | pass | Hotel, retail and restaurant each show "not used by this business" on the others' pages |
| Guest booking page | pass | `/stay/<slug>` at phone width: dates, free rooms, request; HR-2026-0017 reached the desk as an online stay awaiting confirmation |
| Full backend suite and frontend build | CI | Runs on the push to `main` |
| Migration | pass | Whole chain on an empty database, then `20261105_0154` down and up again |
| Restore drill on production, external penetration test | owner | Not done |

## Known limits to tell customers

- Card, Mobile Money and bank tenders are recorded, not charged through a gateway.
- The whole stay is counted as revenue at check-in, not night by night. **Leaving early** on a reservation takes the unused nights off the bill and the books and frees the room.
- A deposit reaches the books when it is taken. On a cancelled or no-show stay it waits under **Deposits to settle** until a cashier or manager gives it back or keeps it. Deposits taken before this release reach the books at check-in as before.
- An event deposit reaches the books only when it lands on a guest's open bill.
- Hotel Reports show room revenue as charged, so with tax inside the rate it includes tax. Accounting and the tax report split it correctly.
- Custom roles copied from a hotel role follow their own permissions, not the job lists.
- Stays closed before this release are not in the books. Open bills catch up on their next payment or at checkout.
- The rate model holds one nightly figure, so a blended rate can round by a pesewa over a long stay.
- There are no hotel tutorial videos yet.
- Money owed lists open bills as they stand today, not for the dates chosen. Guests who already left are on Guest invoices. Rooms that sold nothing in the period are not listed.
- **Edit stay** does not reprice by itself. The price per night stays as shown until staff change it, and the window says so.
- The server still allows a check-in into a dirty room or before the arrival date. The desk warns; it does not block.
