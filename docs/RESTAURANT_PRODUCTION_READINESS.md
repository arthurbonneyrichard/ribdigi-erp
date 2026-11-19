# Restaurant production readiness

**Date:** 30 October 2026 UTC.

**Verdict: Ready to sell to restaurants once this work passes CI and is promoted to `production`. Verified by evidence, not certified.** The same two owner actions as retail remain before anyone may call it certified (external penetration test, production restore drill).

**Re-checked 5 November 2026:** every restaurant page walked signed in with no crash, junk text or sideways scroll; books balance on the demo company; retail and hotel pages closed to a restaurant company; CI green on `0bda9f569a`. Verdict stands once `main` is promoted: the till, digital menu and passcodes are not on production yet.

Restaurant front of house is its own desk, isolated from retail and hotel (`RESTAURANT_FRONT_OF_HOUSE_SPLIT.md`). The back office (ingredient stock, purchasing, accounting, tax, reports) is the shared engine, kept per company by `tenant_id`.

| Gate | Status | Evidence |
| --- | --- | --- |
| Own till, shifts and cash drawer | done | `/restaurant/till`; `restaurant_till_shifts`, `restaurant_till_cash_moves`; `tests/test_restaurant_till_shift.py` |
| Own Orders, Bills and Guests screens | done | `/restaurant/orders`, `/restaurant/bills`, `/restaurant/guests`; `tests/test_restaurant_till_isolated.py` |
| Retail till refused for restaurants | done | `/pos/*` → 403 for a restaurant company; sidebar has no `/pos`, `/sales`, `/customers` |
| Restaurant, POS, hotel test files | pass | 294 passed locally (30 Oct) plus the new shift / guest / isolation tests (11 passed) |
| Migrations | pass | `20261030_0150` + `20261030_0151` up, down, up on a local database |
| Signed-in browser walk (desktop 1440×900 and tablet 820×1180) | pass | Open shift with GH₵200 float → dine-in with an extra and a kitchen note, sent → takeaway paid cash with change → cash in GH₵50 → Orders board → pay from Orders by card → Bills, refund → Till shifts → Guests → count and close (GH₵330.50 expected, short GH₵30.50 shown). No page errors; no failed API calls. |
| Full backend suite and frontend build | CI | Runs on the push to `main` |
| Restaurant website walk (desktop and phone 390×844) | pass | Menu → bag → delivery checkout by Mobile Money with an allergy → tracking → book a table for 4 with a pre-order. Order R-0018 and booking B-0004 arrived on the desk with phone, address, allergy and pre-order. No page errors. |
| Restore drill on production (RPO/RTO) | owner | Not done |
| External penetration test | owner | Not done |

## What a restaurant gets

- **Till:** dine-in by table, takeaway and delivery; extras and kitchen notes; send to kitchen; pay by cash (quick amounts, change), card, Mobile Money or wallet. Money is only taken with an open shift.
- **Shift and drawer:** opening float, cash in and cash out with a reason, live "cash in drawer", count and close with over / short. Cash refunds come out of the drawer.
- **Orders:** a live board (not sent yet, in the kitchen, ready to serve) with wait timers, allergy and rush flags, and one-tap send, add dishes, take payment, cancel or void. Seat, course and pager details stay in the full order editor.
- **Bills:** takings by day and payment method, refunds, and every till shift with its count.
- **Guests:** built from orders and bookings: visits, spend, favourite dish, allergy, bill history.
- **Back-of-house desks** (redesigned 30 Oct): Dashboard (quick desks, today's figures, alert pills), Tables and floor (status floor, one Save per table), Website and booking (website card, bookings as time cards, seat in one step), Kitchen (kitchen display: tickets by age, Start / Ready per dish, All ready), Recipes (dishes with no recipe, one Save per recipe), Waste (reason chips, history). Each desk refreshes only what it shows.
- **Website** (`/order/<slug>` and `/book/<slug>`, one page): the menu with photos and descriptions, a bag, checkout for pickup or delivery (name, phone, address and area, pickup time, cash / Mobile Money / card on collection, allergy, kitchen note), live order tracking (received, in the kitchen, ready, done), and table booking with an optional "have my food ready" pre-order. Website orders show on the Orders board marked Online; bookings land on the booking desk. Turned on under **Website and booking** (`GET|POST /public/restaurant-site/<slug>…`, own rate-limit bucket).

## Known limits to tell customers

- Card, Mobile Money and wallet are recorded, not charged through a gateway.
- Restaurant till sales made before the split (on the old shared till) stay as read-only history in reports.
- A bill can be paid by more than one method (split payment); the amounts must add up to the bill. Each method is recorded on its own.
- The Orders board checks for changes every 4 seconds and reloads in full each minute; it is polling, not push-live.
- The website takes no online payment; guests pay on collection, on delivery or at the table. A pre-order with a booking is a note for the kitchen, rung on the till when the party sits.
- Online booking needs the website or domain saved under Website and booking; the domain itself is pointed by the owner (no DNS change from the ERP).

## Tips (`restaurant_tips.py`, `restaurant_tips_api.py`, screen `/restaurant/tips`)

- The till's payment step has an optional **Tip**. It is booked separately from the sale: the money (cash, card or Mobile Money) is debited and **2187 Tips Owed to Staff** credited. It is never revenue or taxed as sales. Cash tips are in the drawer, so the shift's expected cash includes them (`cash_tips`, `tips` on the shift).
- A refund gives back the bill, not the tip.
- Offline sales take no tip (the tip box is hidden offline).
- A manager (company admin or restaurant manager) shares out the unshared tips of a run of days: **to whoever served** (the waiter who opened the bill), **evenly** between chosen staff, or **by hours** each clocked in HR (needs their staff record with the same email). Rounding leftovers go a pesewa at a time to the biggest shares, so the shares add up exactly.
- Someone who gets no share approves it (**403** `TIPS_SECOND_PERSON`). Then it is paid in **cash** (one payment clears 2187) or **on the payslip** of a chosen month (see `docs/HRM_DESK.md`).
- A draft, or an approved share-out not yet paid or on a payroll, can be cancelled; its tips go back to be shared.
- Every staff member sees their own shares under **Tips**.

## Added 15 Nov 2026

- One bill paid more than one way (cash + card + Mobile Money), booked tender by tender; the drawer counts only the cash part.
- Split a bill by dish or seat onto a new bill for the same table.
- Happy hours: a percentage off chosen dishes (or the whole menu) on chosen days and times.
- The Orders board and kitchen see changes within about 4 seconds (they check for changes and reload only then).
- Mobile Money prompts through the restaurant's own Paystack account; a prompt pays one bill only.
- Still recorded, not charged: card payments (taken on the bank's card machine). Delivery apps (Glovo, Bolt Food) are not linked.

## Kitchen and bar orders: screen, printer or both

- **Choice (company-wide):** Settings → Printers → **Kitchen and bar orders** (`GET|PUT /restaurant/ticket-delivery`, stored in `tenants.document_numbering["restaurant_ticket_delivery"]`, audited). Managers and company admins only; waiter, cashier and kitchen roles are refused by the restaurant job gate.
  - **Screen and printer** (default): the kitchen screen shows each order and tickets print on any enabled Kitchen or Bar printer.
  - **Screen only:** nothing prints; the kitchen screen still gets the order.
  - **Printer only:** tickets print and the kitchen screen shows a note instead of the board. Refused (409) until an enabled printer with the Kitchen or Bar purpose exists.
- **Printers:** on Settings → Printers a restaurant can link an installed printer for till receipts, kitchen tickets only, bar tickets only, or kitchen and bar. Kitchen dishes print on Kitchen printers and drinks on Bar printers; extras print under the dish; dishes added later print as a new ticket; sending twice prints nothing new.
- **Printer only and the orders board:** nobody taps Start, so a ticket that reaches paper (network printer, paired till, or the screen's own printer) moves that station's ticket and dishes to *preparing* and a just-sent order to *preparing* (`restaurant.printed_ticket_starts_cooking`). Nothing is ever marked *ready* by printing. With a screen in use the cook's Start tap still decides.
- **Limits to tell customers:** a printer plugged into a tablet or PC prints only while that screen has **Print tickets here** switched on (checks every 10 seconds). Network and paired-till printers print by themselves. A printer problem never stops an order. Verified by automated tests and the browser print dialog; confirm a physical printer with a test print before go-live.
- Tests: `backend/tests/test_restaurant_prep_printing.py`. Tutorials: R12, R34 and R39.
