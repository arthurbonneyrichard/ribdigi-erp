# Bakery desk

A bakery is its own industry. Its sales, orders, recipes, batches, waste and till live on `bakery_*` tables. It never writes to retail `transactions` or `pos_sessions`, and the retail till, hotel and restaurant desks refuse a bakery company.

## Sidebar

A bakery company gets its own sidebar (`BAKERY_NAV_GROUPS` in `frontend/lib/tenantNav.ts`): Dashboard; Selling (Counter, Orders, Deliveries, Trade customers); Kitchen (Baking, Waste); Stock and money (Stock, Expenses, Reports); Staff; Notifications; Help; Settings. No retail Inventory, Purchases, Finance or Reports menus, and no in-page tab strip: the sidebar is the only menu.

## Screens (`/bakery`)

- **Today:** orders due, batches baked, sales, waste, profit after waste, what to bake for orders due by tomorrow.
- **Counter:** the till. A shift must be open. Cash, card, Mobile Money or wallet.
- **Orders:** pre-orders with a collection date and a deposit.
- **Baking:** recipes and bakes.
- **Waste:** unsold, burnt, damaged, past its date, other.
- **Deliveries:** orders going out by driver; drivers out and the cash they should hand in.
- **Stock:** items for sale and ingredients, low-stock warnings, buying stock in (cash, Mobile Money, bank, card, or owed to the supplier).
- **Expenses:** rent, wages, light and water, gas, transport, repairs, packaging, marketing, other. Cash can come out of the till.
- **Reports:** period presets, the period before for comparison, profit and loss down to net profit, item by item with cost and margin, busy hours, how customers paid, waste by item, orders and deposits held, stock bought and worth, till and cash bag counts. Print and CSV.

Ingredients and items for sale are ordinary products under Inventory. An item with a selling price shows at the counter. Ingredients keep a selling price of 0.

## Money

- Every movement of money is a row in `bakery_payments`, so the drawer is one sum.
- A bake moves value from ingredients to finished goods at recipe cost.
- A deposit is owed to the customer until collection: debit money, credit **2168 Customer Deposits (Bakery Orders)**, a liability. Collection recognises the revenue. Do not book it a second time. Deposits taken before 15 Nov 2026 sit in 1100; `bakery_orders.deposit_account` NULL means 1100 and collection or cancelling clears that account.
- Cancelling with a deposit asks whether to give it back or keep it. A kept deposit is booked to **4400 Other Income** (it pays for no goods). Whether VAT is due on a kept deposit is for the company's accountant.
- Waste posts to the books at cost.
- Buying stock in: the unit cost is before VAT; VAT on the supplier's bill goes to **1300 Input Tax** and on the VAT return. Stock is valued without it.
- Expenses go to their own accounts: rent 6010, wages 6200, light and water 6030, gas 6040, transport 6050, repairs 6060, packaging 6070, marketing 6080, other 6000. VAT inside an expense goes to 1300; reports show the cost before VAT.
- Till close and driver hand-in: the gap between counted and expected cash is booked to **6900 Cash Over and Short** against 1000, so the cash account matches the drawer.
- Stock count (`POST /bakery/stock/count`, manager): each counted item is set to what is there; the value gained or lost goes to **5100 Stock Count Differences** against 1200.
- Tax report: bakery sales count on their own day as output tax; a refund is a credit on the day it happened, so a filed month never changes. Bakery stock receipts and expenses with VAT are input tax. Bakery companies only.

## Counter extras

- **Discounts:** `discount_percent` per line comes off the price before tax, with a `discount_reason`. Cashiers and drivers up to 10% (`STAFF_MAX_DISCOUNT`), managers and owners any amount (403 `DISCOUNT_TOO_BIG`). Not offline.
- **Two ways to pay:** `payments` (2–4 parts). One part may leave its amount out and takes the rest; otherwise the parts must equal the bill (422 `SPLIT_NOT_EQUAL`). The sale's `payment_method` is `split`. Not offline.
- **Refunds:** whole sale or chosen lines and quantities (`bakery_refunds` + `bakery_refund_lines`); status `part_refunded` until everything is back, then `refunded`. A collected order is refunded the same way. A split sale needs the refund `method`; a cash refund cannot be more than the drawer should hold.

## Order slip, ready text and production sheet

- **Order slip** (`GET /bakery/orders/{id}/print`, Orders → Print slip): company details, customer, collection or delivery, each line with its writing/note, total, deposit paid and what to pay on collection. Not for bakers (cashier, manager, owner).
- **Ready text:** `POST /bakery/orders/{id}/ready` texts the customer (when the order has a phone) through the company's SMS settings: "your order is ready", with the balance to pay. It is best effort: the order is marked ready either way and the response carries `customer_texted {sent, reason}`, which the screen shows ("Customer not texted: SMS is not set up"). Set SMS up under Company → SMS; with none it runs in the console in development and is skipped in production.
- **Production sheet** (`GET /bakery/production-sheet/print`, Today → Print production sheet): what to bake (orders, trade, shelf level, on hand) and the orders due today and tomorrow with their writing. No prices, so bakers may print it.
- Tests: `test_bakery_slips_and_texts.py`.

## Regulars and birthday texts (`/bakery?tab=regulars`)

`bakery_regulars.py`, table `bakery_regulars` (migration `20261119_0203`). Regulars are found from the phone numbers on orders (cancelled orders do not count), so there is no second customer list: `GET /bakery/regulars` gives orders, spend and last order per phone, biggest spenders first.

- `PUT /bakery/regulars` sets a name, a birthday (month and day together; impossible dates are refused; 29 Feb is celebrated on 28 Feb in common years) and `texts_ok`. A phone with no order yet is 404. Cashiers and managers may edit; bakers and drivers cannot see the list.
- `GET /bakery/regulars/birthdays?days=` lists coming birthdays (default 14).
- `POST /bakery/regulars/birthday-texts` (manager) texts today's birthdays **only if `texts_ok`**, once per year each (`last_text_year`), through the company's SMS settings. It reports `sent`, `already_texted` and `failed` with reasons; with no SMS set up nothing is marked as texted.
- Never text anyone who has not agreed. Tests: `test_bakery_regulars.py`.

## Quotes

An order taken with `quote: true` (Orders → "Just a quote for now") is a quote: status `quote`, number `BQ-…`, no deposit (422), not in `ORDER_OPEN`, so nothing is planned, baked or delivered for it. `GET /bakery/orders?show=quotes` lists them (Orders → Quotes); the slip prints as "Quote".

- `POST /bakery/orders/{id}/confirm-quote` `{deposit, method}` makes it a booked order with a real `BO-…` number. An optional deposit goes through `add_deposit`, so it needs an open till; a refused confirm leaves it a quote. A past collection day is refused (422).
- `POST /bakery/orders/{id}/decline-quote` `{reason}` sets status `declined`. Anything that is not a quote is 409. Test: `test_bakery_regulars.py::test_quote_confirm_and_decline`.

## Part-payments on big orders

`POST /bakery/orders/{id}/part-payment` `{amount, method}` (Orders → Take payment) takes another instalment on an open order, for wedding and event cakes paid in stages. It needs an open till, cannot exceed what is still owed (422), and books Dr money / Cr the order's deposit account (2168; 1100 for old orders) exactly like the first deposit, so collection still turns the whole deposit into revenue once. A cancelled or collected order refuses it (409).

Cancelling with `deposit_action=refund` gives each instalment back the way it came in (`bakery.add_deposit`, `_deposit_parts`: one credit line and one `deposit_refund` payment per method); a kept deposit still goes to 4400. Test: `test_bakery_regulars.py::test_part_payments_and_refund_by_method`.

## Cake and order options

A manager gives an item option groups under Stock → Item details (`options` on `PUT /bakery/items/{id}/details`, stored in `bakery_item_settings.options`, migration `20261119_0202`). One line per group: `Size*: 6 inch, 10 inch=60` (`*` = must be chosen, `=60` = extra price before tax).

- An order line may carry `options: [{group, choice}]`. `bakery.apply_options` checks each against the item's own list (422 for an unknown group or choice), adds the extra to the unit price before discount and tax, and writes `Size: 10 inch; Flavour: Red velvet` ahead of the customer's writing in the line note (so the order slip, production sheet and delivery show it).
- Required groups are enforced on orders (`enforce_options`), not at the counter: counter sales may pass `options`, but a counter line without them is sold at the base price. The counter basket is one line per item, so custom cakes (size, flavour, writing) are taken under Orders, which also holds the date and deposit.
- Prices always come from the item's list, never from the request. Tests: `test_bakery_safety.py::test_cake_options_price_and_note_an_order`.

## Food safety (`/bakery?tab=safety`)

`bakery_safety.py`, tables `bakery_safety_points`, `bakery_safety_readings`, `bakery_safety_checks` (migration `20261119_0201`). Nothing here touches the books.

- **Points:** a fridge, freezer, display, oven, proofer or other, each with a safe range in °C (kind defaults: fridge 0 to 5, freezer −25 to −18, display 0 to 8, oven 160 to 260, proofer 25 to 40) and checks per day. A manager adds and edits them (`POST|PATCH /bakery/safety/points`); a switched-off point takes no readings.
- **Readings:** `POST /bakery/safety/readings`. A reading outside the range must say what was done about it (400 otherwise); it is saved with `in_range=false`. Bakers and cashiers may record.
- **Checklists:** opening, closing, deep clean and delivery (`bakery_safety.CHECKLISTS`). `POST /bakery/safety/checks` signs one with the lines ticked; it counts as done for the day only when every line is ticked.
- **Today:** `GET /bakery/safety` shows each point's last reading, readings still due, bad readings and which checklists are done.
- **Inspector record:** `GET /bakery/safety/print?start_date&end_date` (default last 30 days) prints every reading and checklist, bad readings in bold. `GET /bakery/safety/history` is the same data as JSON.
- **Dashboard:** bad readings and readings still to take show under "Needs you now" on Today.
- Tests: `test_bakery_safety.py`. Ranges are typical values: the company should confirm them with its own food safety plan.

## Shelf life, day-old and labels

Item details (`PUT /bakery/items/{id}/details`, manager; Stock → Item details), stored in `bakery_item_settings`:

- **Shelf life:** each bake gets `best_before` = baked day (company timezone) + shelf life. `GET /bakery/shelf` assigns today's stock to the newest bakes (oldest sell first) and marks each bake fresh, day-old, last day or past its date. Past-date stock is left out of "what to bake" and flagged on the dashboard.
- **Day-old price:** `day_old_discount_pct`. A counter line with `day_old: true` takes it, for as much day-old stock as there is, and any cashier may use it (a manager set the price). Reason is "Day-old".
- **Allergens:** the 14 declarable allergens (`bakery_items.ALLERGENS`). A label shows the item's own allergens plus those of every recipe ingredient. Ingredients are listed largest first by weight; ingredients that carry an allergen are in bold. `GET /bakery/items/{id}/label?batch_id=&copies=` prints labels with best before, batch, net weight, storage note and price.

## Units and shelf level

- An ingredient has a stock unit (kg, g, l, ml, each) and may have a purchase unit (`purchase_unit`, `units_per_purchase`, e.g. a 50 kg bag). Buying with `in_purchase_units` turns bags into kg and the bag price into a kg cost. Recipe lines may be written in another unit of the same kind (`unit: "g"` for a kg ingredient) and are stored in the stock unit. Cost prices keep 2 decimals, so keep flour in kg, not g.
- `par_level` is how many to have on the shelf each day. What to bake = open orders due by tomorrow + today's trade standing orders not yet made + shelf level − in-date stock.

## Tills

Several tills can be open at once, each with a name (`till_name`, default "Counter"); one person runs one till. A request uses the till in header `X-Bakery-Till` (the shift id; the screen keeps it per device in `lib/bakeryTill.ts`), else the till the signed-in person opened, else the only one open; otherwise 409 `TILL_CHOOSE`. `GET /bakery/tills` lists the open ones. The choice is set per request in `bakery_api._till_context` (context variables `CHOSEN_TILL`, `TILL_USER`).

## Trade customers (`/bakery?tab=trade`)

`bakery_trade.py`. Customers (`bakery_customers`) have a credit limit (0 = none), a trade discount off the shop price, and days to pay. Standing orders say how many of an item on which weekdays. **Make today's deliveries** (`POST /bakery/trade/run`) makes one invoice per customer per day from standing orders; an invoice takes stock and books Dr 1100 / Cr 4000, 2100 with cost of goods. Over the credit limit → 409 `CREDIT_LIMIT` unless a manager sends `override_limit`. A payment clears the oldest invoices first (cash goes into the till). A void (unpaid only) reverses the books on the day of the void, and the goods come back only if `restock`. Statements show opening balance, lines, closing balance and what is owed by age. Trade invoices count in the bakery report (`trade_revenue`) and on the VAT return by invoice day; voids by void day. Cashiers make deliveries and take payments; customer setup, voids and credit overrides need a manager.

## Suppliers

`bakery_suppliers`. Buying on credit needs a supplier (a typed name is found or added). What you owe = credit purchases with VAT − payments. `POST /bakery/suppliers/{id}/payments` books Dr 2000 / Cr money; cash can come from the till.

## Drivers

A driver (`bakery_driver`) picks up delivery orders, delivers them, takes the balance, and sells from the van. Their money goes into their own cash bag (a `bakery_till_shifts` row with `kind="driver"`), never the counter till. A bag must be started before picking up or selling. Delivery is the same as handing an order over: stock leaves and revenue is booked then. A failed delivery comes back to the shop and moves nothing. Someone else (cashier or manager) counts the bag at hand-in, and it cannot be handed in while a delivery is still on the road. Drivers see no profit or costs.

Managers and owners sometimes drive (`DRIVE_ROLES` in `bakery.py`). They start a cash bag from Deliveries ("Start driving"), pick up, deliver and take the money into it, and sell from the van by choosing "My van bag" at the counter (`from_bag` on the sale). A manager covering for a driver may take over a delivery that has not left the shop. A manager or owner may count their own bag; the audit record marks it as counted by themselves. Drivers still cannot count their own bag or take another driver's delivery.

## Counter prices

The counter shows each item's price with tax (`price_to_pay` from `/bakery/items`), rounded per line the same way the sale is, so the screen, the change and the charge agree.

## Staff jobs

`bakery_api.py` limits each role inside `require_permission("bakery", …)`, and `BAKERY_ROLE_HREFS` in `frontend/lib/tenantNav.ts` mirrors it for menus.

| Role | Can do |
| --- | --- |
| Bakery Manager, company admin | everything, including refunds, order cancels and reports |
| Bakery Cashier | counter, orders, deliveries (assign, take cash in), waste |
| Baker | recipes, bakes, waste; sees no money |
| Bakery Driver | deliveries, selling from the van, their own cash bag; sees no profit |

## Demo

`PYTHONPATH=. python scripts/seed_bakery_demo.py` creates `demo-bakery-rec` (Golden Crust Bakery; owner, cashier, baker and driver logins). It refuses to run in production.
