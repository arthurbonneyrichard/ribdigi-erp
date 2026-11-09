# Bakery desk

A bakery is its own industry. Its sales, orders, recipes, batches, waste and till live on `bakery_*` tables. It never writes to retail `transactions` or `pos_sessions`, and the retail till, hotel and restaurant desks refuse a bakery company.

## Sidebar

A bakery company gets its own sidebar (`BAKERY_NAV_GROUPS` in `frontend/lib/tenantNav.ts`): Dashboard; Selling (Counter, Orders, Deliveries); Kitchen (Baking, Waste); Stock and money (Stock, Expenses, Reports); Staff; Notifications; Help; Settings. No retail Inventory, Purchases, Finance or Reports menus, and no in-page tab strip: the sidebar is the only menu.

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
- A deposit is owed to the customer until collection: debit money, credit 1100. Collection recognises the revenue. Do not book it a second time.
- Cancelling with a deposit asks whether to give it back or keep it as income.
- Waste posts to the books at cost.
- Tax report: completed bakery sales count as output tax, for bakery companies only.

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
