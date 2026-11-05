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
- A deposit reaches the books at check-in, not when it was taken. A deposit on a stay that never arrives is not in the books.
- An event deposit reaches the books only when it lands on a guest's open bill.
- Cash taken on **Guest invoices** after checkout is in the books, but not in the front-desk drawer count.
- Hotel Reports show room revenue as charged, so with tax inside the rate it includes tax. Accounting and the tax report split it correctly.
- Custom roles copied from a hotel role follow their own permissions, not the job lists.
- Stays closed before this release are not in the books. Open bills catch up on their next payment or at checkout.
- The rate model holds one nightly figure, so a blended rate can round by a pesewa over a long stay.
- There are no hotel tutorial videos yet.
