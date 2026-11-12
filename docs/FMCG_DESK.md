# FMCG desk

FMCG is a distributor's desk: it sells to outlets on credit, delivers by van and collects later. It sells on `fmcg_*` tables, not retail Sales documents or the till. Products and customers are the shared back-office masters.

## Sidebar

An FMCG company gets its own sidebar (`FMCG_NAV_GROUPS` in `frontend/lib/tenantNav.ts`): Dashboard; Selling (Outlets, Orders, Deliveries, Collections); Trade (Routes, Trade schemes, Pack convert); Stock (Products, Stock levels, Adjust stock, Stock count, Expiry and batches); Buying (Suppliers, Purchase orders, Receive goods, Supplier bills, Pay suppliers); Money (Expenses, Reports); Staff; Notifications; Help; Settings. One Dashboard entry, no retail Sales, Finance or Reports menus, and no in-page tab strip.

## Screens (`/fmcg`)

- **Overview:** to load, on trucks, delivered, sales, collected, what outlets owe and how much is late.
- **Outlets:** credit limit, days to pay, route, sales rep, balance.
- **Orders:** book, load, deliver, record a failed delivery, take a return, settle a truck.
- **Collections:** payments and returns.
- **Trade schemes, Routes, Deliveries, Pack convert:** set-up and route work.
- **FMCG reports:** net sales, returns, scheme discounts, gross profit, collected, who owes, by route, by rep, best sellers.

## Money

- Prices come from the catalogue. The best running scheme comes off each line.
- **Booking moves nothing.** A credit order counts against the outlet's limit while it is open, so a rep cannot pass the limit one order at a time. Going over needs a manager and a reason.
- **Loading** checks stock not already on another truck. Stock stays ours until delivery.
- **Delivery** books the sale: debit 1100, credit 4000 and 2100, cost of goods, stock out, outlet balance up. Payment-on-delivery orders are collected in the same step.
- **Collection** debits money and credits 1100. It pays the chosen order, then the oldest ones. It cannot exceed what the outlet owes.
- **Return** reverses revenue and tax and credits the outlet. Stock and cost only come back if the goods can be sold again.
- **Settle** compares cash collected on a dispatch with what the driver hands in, records any gap, closes the dispatch and sends undelivered orders back to be loaded.
- Tax report: delivered orders less returns, for FMCG companies only.

## Staff jobs

`fmcg_orders.job` limits each role inside `require_permission("fmcg", …)`, and `FMCG_ROLE_HREFS` in `frontend/lib/tenantNav.ts` mirrors it for menus.

| Role | Can do |
| --- | --- |
| Distribution Manager, company admin | everything |
| Sales Rep | outlets, visits (own territory), orders, collections |
| Delivery Driver | deliver, failed delivery, collections, returns |

## Territories and outlet visits

Tables `fmcg_territories`, `fmcg_territory_routes`, `fmcg_territory_reps`, `fmcg_visits` (migration `20261113_0170`); code in `app/fmcg_field.py` and `app/fmcg_field_api.py`; screens **Visits** and **Territories** (`/fmcg?tab=visits|territories`, `FmcgField.tsx`).

- A territory is a set of routes plus the reps who work it. A route sits in one territory; saving it in another moves it. A rep's outlets are the outlets assigned to those routes (`GET /fmcg/my-outlets`); a rep cannot check in anywhere else (**403** `OUTSIDE_TERRITORY`). Managers see and visit every outlet.
- The rep checks in (`POST /fmcg/visits/check-in`) and out (`POST /fmcg/visits/{id}/check-out`) from the phone. The browser's location and its accuracy are sent at both ends. One open visit per rep at a time.
- A visit is never refused for distance. It is flagged instead: `far` (more than 300 m from the outlet), `rough_gps` (accuracy worse than 200 m), `no_gps` (location refused or unavailable), `outlet_unmapped`, and `order_not_booked` (outcome "order" but the rep booked no order for that outlet during the visit).
- An outlet with no saved location takes it from the first check-in with accuracy 50 m or better (audited as `fmcg_outlet_located`). After that only a manager changes it.
- Outcomes: order, no order (with a reason), shop closed, could not find it. "Order" links the order the rep booked for that outlet since check-in.
- `GET /fmcg/coverage?day=` (managers): per rep visits, orders, strike rate, first in / last out, flagged visits; per route the stops planned for that weekday (`visit_day` blank means every day) and the ones missed. `GET /fmcg/territories/report?period=YYYY-MM`: outlets, outlets reached, visits and delivered sales per territory.
- A tampered phone can fake its location. The stored accuracy, distance and times are what a manager has to judge by.

## Known limit

Retail `/sales` routes still answer for an FMCG company, because schemes also apply there and older tests use them. The menu no longer shows them.

## Demo

`PYTHONPATH=. python scripts/seed_fmcg_demo.py` creates `demo-fmcg-rec` (Northern Star Distributors; owner, rep and driver logins). It refuses to run in production.
