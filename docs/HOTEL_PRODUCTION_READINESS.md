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

## Full audit, 6 November 2026

Every test below is in `tests/test_hotel_audit_2026_11.py`. 105 hotel tests passed before this audit, so none of these were being caught.

| Area | Finding | Now |
| --- | --- | --- |
| Backups | No hotel table was in a company backup, so a restore lost rooms, guests, stays and bills | All 20 hotel tables are backed up and restored; date columns now restore correctly |
| Tax | VAT on shop sales paid at the till never reached the tax filing | In the filing. A sale charged to a room is counted once, on the guest's invoice |
| Rooms | A second guest could check into a room whose guest had overstayed | Refused until the first guest leaves or moves |
| Rooms | Taking a room off sale stranded its guest: no check-out, no bill | Refused while a stay is on the room, and old cases can still finish |
| Rooms | Room status could be changed under a guest; a room could be marked occupied with nobody in it | Refused |
| Rooms | A fault reported during a stay could leave the room stuck as dirty; fixing a dirty room marked it clean | Clean and repaired are tracked apart, and the room returns when both are done |
| Rooms | Closing a repair crashed with two other tickets open on the room | Fixed |
| Stays | Checking in days early left the stay on its future dates, so the room looked free tonight and could be sold again | The room must be free until the booking starts, and an in-house guest holds the room from today. Dates and bill stay as booked, and the desk says to use Edit stay first for extra nights |
| Stays | Move and Edit ignored room size; a room in use tonight could not take next week's booking | Size is checked; only the stay's own dates matter |
| Stays | Overstaying guests and arrivals that never came showed nowhere | On departures and in alerts |
| Bills | Moving a tax-inclusive charge added the tax again | The amount is kept |
| Bills | A Discount line added to the bill | It takes money off the bill and the books, and cannot exceed the bill |
| Bills | A tax line posted to revenue | It posts to tax |
| Bills | Service charge stayed the same when nights changed | It follows the room charge |
| Bills | On-account counted as money received; a guest in credit hid what others owed | Both corrected on the dashboard, reports and float |
| Bills | Check-out crashed when two customers shared a name | Fixed |
| Deposits | A no-show fee and a kept deposit counted the same money twice | The deposit pays the fee first, using its original journal |
| Deposits | A no-show bill could never be closed or chased | **Close bill** refunds or keeps what is left, and moves what is owed to Guest invoices |
| Cash | A shop refund on a later float never left that drawer | It comes out, and cash refunds need an open float |
| Shop | Could charge a no-show or cancelled guest; accepted another company's store | Refused |
| Staff | Housekeeping could read guest ID numbers, phones, rates and bills | Refused or removed |
| Staff | A clerk could sign off their own discount, up to 100% | Cashier or manager only, and the approver must be a real user. Rate changes are in the audit log |
| Online | The booking reply showed a known guest's email; a returning guest on a new phone was refused | The reply says nothing about the guest record, and returning guests can book |
| Online | Rooms were offered and then refused, or hidden for a repair on other dates | Same rules as the desk |
| Online | Requests could hold rooms without limit | 60 nights, one year ahead, three open requests per guest, and its own rate limit |
| Data | Events, lost items and requests could point at another company's records | Refused |
| Data | Merging guests left events and the email behind | They move to the kept guest |
| Data | Two desks could take the same reservation, bill or sale number | Numbers are taken one at a time per company |
| Settings | Free cancellation of 0 hours came back as 24; bad times and percents above 100 were accepted | Fixed |
| Lists | Old debts could fall off Guest invoices behind newer paid ones | The list is taken from what is owed |

## Company backups, 6 November 2026

Backups covered 60 of 170 company tables and restore had only ever run over rows that still existed. Now every company table is either backed up or named in `backup.BACKUP_EXCLUDED` with its reason, and `tests/test_backup_coverage.py` fails on a new table that is neither.

- **Added:** hotel, restaurant, sales orders, quotations, returns, branches, departments, customer groups, price tiers, cash transfers, gift cards, till cash movements, ecommerce orders and storefronts, FMCG and hospital records.
- **Left out on purpose:** users and everything used to sign in, the audit log, device pairing, webhooks, short-lived working data, and RIBDIGI's own billing and support records.
- **Restore order** is worked out from the links between tables, and links that point forward are filled in at the end.
- **A failed restore** now undoes itself and reports the reason.
- **After a restore from nothing:** staff logins are untouched. Ecommerce shoppers lost in the disaster reset their password, and webhooks, API keys, printers and till passcodes are set up again.
- **Drill on Postgres:** a hotel (626 rows) and a restaurant (74 rows) were emptied and restored, with every table count and the trial balance matching. This has not been run on production: that drill is still the owner's to do.

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
- A deposit reaches the books when it is taken. On a cancelled or no-show stay it waits under **Deposits to settle** until a cashier or manager gives it back or keeps it, or until a no-show fee takes it. Deposits taken before this release reach the books at check-in as before.
- An event deposit reaches the books only when it lands on a guest's open bill.
- Hotel Reports show room revenue as charged, so with tax inside the rate it includes tax. Accounting and the tax report split it correctly.
- Custom roles copied from a hotel role follow their own permissions, not the job lists.
- Stays closed before this release are not in the books. Open bills catch up on their next payment or at checkout.
- The rate model holds one nightly figure, so a blended rate can round by a pesewa over a long stay.
- There are no hotel tutorial videos yet.
- Money owed lists open bills as they stand today, not for the dates chosen. Guests who already left are on Guest invoices. Rooms that sold nothing in the period are not listed.
- **Edit stay** does not reprice by itself. The price per night stays as shown until staff change it, and the window says so.
- The server still allows a check-in into a dirty room. The desk warns; it does not block.
- Checking in before the arrival date keeps the booked dates and bill. For extra nights, use Edit stay first.
- A discount line reduces revenue, not tax, so VAT on a discounted stay stays at the full amount until an accountant adjusts it. That can only overstate tax.
- A closed bill cannot be changed. A mistake found after check-out needs an accountant's journal.
- The hotel's "today" is the server's date, which is UTC. That is right for Ghana. A hotel in another timezone rolls over at the wrong local hour.
- Weekend rate applies to Saturday and Sunday nights.
- A repair dated ahead closes the room for bookings straight away, but the room's status changes only when someone next touches it. The dashboard and check-in already treat it as closed on the day.
- An online request holds its room until staff confirm or cancel it. There is no automatic expiry.
