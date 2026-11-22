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

## Batches, expiry and recalls

Code in `app/fmcg_batches.py` + `app/fmcg_batches_api.py`; screens **Batches and expiry** and **Recalls** (`/fmcg?tab=batches|recalls`, `FmcgBatches.tsx`); migration `20261120_0214f`. Managers and admins only (`fmcg_orders.job` area `batches`).

- **Delivery is first-expiry-first-out.** `deliver_order` goes through `catalog.stock_out_with_batch`: expired, quarantined and recalled batches are refused (**409**), and each line's batches are saved in `fmcg_line_batches`.
- **Returns** that can be resold go back onto the batch they came from, unless it is held or expired.
- **Warning days** per company (`GET|PUT /fmcg/batch-policy`, default 90/60/30/14/7, stored in `tenants.document_numbering["fmcg_batch_policy"]`). `GET /fmcg/batches?status=ok|near|expired|held`.
- **Hold / release** reuse `batch_holds`. **Write-off** (`POST /fmcg/batches/{id}/write-off`) needs an expired or held batch, takes stock out and posts Dr 6000 Cr 1200 at cost.
- **Recall:** opening one holds the batches and lists every outlet and order that received them. Recovery is capped at what is still out; a recalled batch cannot be released until the recall is closed.
- Not yet: near-expiry discounts, per-category warning periods, FIFO policy switch.

## Van sales

Code in `app/fmcg_van.py` + `app/fmcg_van_api.py`; screen **Van sales** (`/fmcg?tab=van`, `FmcgVan.tsx`); tables `fmcg_van_loads`, `fmcg_van_expenses`, `fmcg_van_closings` (migration `20261120_0215f`). A van is an open dispatch.

- **Load** (`POST /fmcg/dispatches/{id}/van/load`) sets stock aside. Loaded-and-unsold stock is reserved: other loads and warehouse deliveries cannot take it (`fmcg_orders.van_reserved`).
- **Sell** (`POST .../van/sales`) books and delivers in one step from the van's remaining stock (**409** `NOT_ON_VAN`). Cash orders need a payment method; credit orders obey the outlet's credit limit. Revenue, tax, COGS and FEFO batch use are the same as any delivery.
- **Losses** (`.../van/losses`, damaged or sample) take stock out and post Dr 6000 Cr 1200 at cost. **Costs** (`.../van/expenses`) post Dr 6000 Cr cash and reduce the cash to hand in.
- **Close** (`.../van/close`): the crew counts every loaded product and the cash. Expected left = loaded - sold - damaged - samples. Any stock or cash difference needs a manager (**403** `VAN_VARIANCE_NEEDS_MANAGER`) and a written reason; the stock difference is posted as a loss or gain, then the dispatch settles as before.
- `GET .../van` is the live reconciliation; `GET /fmcg/van/performance` is one row per trip (managers). Reps and drivers can sell, record and close a clean van.
- Customer returns still go back to warehouse stock, not to the van.

## Quality control and proof of delivery

Code in `app/fmcg_quality.py` + `app/fmcg_quality_api.py`; screens **Proof of delivery**, **Quality control** and **Complaints** (`/fmcg?tab=pod|quality|complaints`, `FmcgQuality.tsx`); tables `fmcg_proofs_of_delivery`, `fmcg_qc_inspections`, `fmcg_complaints` (migration `20261120_0216f`).

- **Proof of delivery:** `POST /fmcg/orders/{id}/pod` after delivery (recipient name plus a signature and/or photo, optional location). One per order (**409** if repeated). Images are PNG/JPEG data URLs, checked for real file signatures and size (signature 150 KB, photo 800 KB, **413** over), and stored in the database. `GET /fmcg/pod/missing` lists delivered orders with no proof. Drivers and reps can capture; the signature pad is `SignaturePad` in `FmcgQuality.tsx`.
- **Inspections:** product, optional batch and supplier, packaging/label/expiry checks, temperature, certificate reference. `hold_until_decided` puts the batch on a quarantine hold. A pass is refused while a check is marked failed (**409** `CHECK_FAILED`) and releases only the hold that inspection placed; a recall hold is never touched. A fail needs a reason, keeps the batch held and can record the rejected quantity. Supplier pass/fail history: `GET /fmcg/quality/suppliers`.
- **Complaints:** reps and drivers can log them against an order, product and batch; managers investigate and resolve or reject (resolution text required). Each row shows how many complaints the same batch has, a cue to open a recall.
- Managers and admins run inspections; reps and drivers get **403** there.
- Not yet: image storage outside the database, quality certificates as file uploads, automatic credit notes from a resolved complaint.

## Promotions

Code in `app/fmcg_promos.py` + `app/fmcg_promos_api.py` (`/fmcg/promotions`), pricing in `fmcg.best_line_scheme_discount`; screen **Promotions** (`/fmcg?tab=promotions`, `FmcgPromotions.tsx`); migration `20261120_0217f` adds status, budget, use limit, minimum quantity and approval fields to `fmcg_trade_schemes` and the table `fmcg_scheme_targets`. Managers and admins only.

- **A scheme applies to a line only when it is:** approved and running, inside its dates, matching the product (or product category), at or above its minimum quantity, open to the outlet, and with budget and uses left. Only the single best scheme applies, so schemes never stack.
- **Approval:** a percent scheme above the company limit (default 30%), or a budget above the budget limit, is created `pending` and prices nothing until someone other than its creator approves it (**409** `SECOND_PERSON_NEEDED`). Limits: `GET|PUT /fmcg/promotions/policy`. The older `POST /fmcg/schemes` follows the same rule. A company with a single manager must raise the limit or add a second approver.
- **Who it is for:** targets of kind outlet, route or territory; no targets means everyone. An outlet's route comes from its assignment, its territory from that route.
- **Budget and use limit:** spend and uses are read from live FMCG order lines (cancelled orders give the money back), with the scheme row locked while pricing and a running total across lines of one order, so a promotion cannot overspend. Retail sales that use schemes are not counted against the budget.
- **Results:** `GET /fmcg/promotions/{id}/performance`: committed discount, delivered units and outlets, discount given, sales after discount, cost of goods (at each product's current cost), gross profit and margin, budget used.
- Buy X get Y is given as a price reduction equal to the free units; free goods are not shipped as a separate stock line. Editing a running promotion is not supported: stop it and make a new one.

## Warehouse zones and bins

Code in `app/fmcg_warehouse.py` + `app/fmcg_warehouse_api.py`; screen **Warehouse layout** (`/fmcg?tab=warehouse`, `FmcgWarehouse.tsx`); tables `fmcg_locations`, `fmcg_bin_stock`, `fmcg_bin_counts` (migration `20261120_0218f`). Managers and admins only.

- **Layout:** a warehouse has zones (ambient, cold, bulk, quarantine, receiving, dispatch, returns) and bins inside zones, each with a label code (unique per warehouse, case-insensitive) and an optional capacity. A bin or zone can only be switched off when empty.
- **Bins are a location layer over consolidated stock.** Put-away, moves and counts never change how much stock the company has and post nothing to the books. Put-away is limited to stock not yet in any bin (`NOT_ENOUGH_UNPLACED`); per batch it uses that batch's quantity.
- **Rules:** a bin cannot go over its capacity (`BIN_FULL`); a held or expired batch can only go in a quarantine zone (`QUARANTINE_ONLY`) and a quarantine zone takes only such stock (`NOT_QUARANTINED`); moves stay inside one warehouse (use a stock transfer between warehouses).
- **Stock leaving takes it out of the bins** (`consume`, earliest pick order first, never from quarantine): FMCG delivery, batch write-off and van damage/samples. Stock that leaves another way, such as a retail sale or a van count shortage, can leave a bin over-stated; `GET /fmcg/warehouse/report` lists those products under over-binned so a count fixes them.
- **Counts:** `POST /fmcg/locations/{bin}/count` sets a bin to what was counted. A difference needs a written reason; something missing from the sheet counts as zero; finding more than the system has unplaced is refused (`MORE_THAN_STOCK`: fix the stock level first). `?blind=true` on contents hides quantities for a blind count. Every difference is kept in `fmcg_bin_counts`.
- **Guidance:** `GET /fmcg/orders/{id}/pick-list` shows which bins and batches to pick from, earliest expiry first, skipping held, expired and quarantined stock, and how much is not in any bin. `GET /fmcg/warehouse/suggest` proposes bins for put-away. `GET /fmcg/locations/scan?code=` opens a bin by its label; a USB or Bluetooth scanner works as a keyboard in the scan box.
- Not yet: scanner-confirmed pick tasks, wave picking, putaway from goods receipts automatically, a storekeeper role, per-bin pallets.

## Fleet

Code in `app/fmcg_fleet.py` + `app/fmcg_fleet_api.py`; screen **Fleet** (`/fmcg?tab=fleet`, `FmcgFleet.tsx`); tables `fmcg_vehicles`, `fmcg_vehicle_logs` and `fmcg_dispatches.vehicle_id` (migration `20261120_0219f`). Managers and admins only.

- **Register:** plate (unique per company, upper-cased), type, driver, odometer, insurance / roadworthy / licence expiry, service interval. Each document is ok, expiring (30 days), expired or not recorded; `GET /fmcg/fleet/attention` lists expired and expiring documents and services due.
- **Dispatch:** `POST /fmcg/dispatches/{id}/vehicle` refuses a vehicle that is not active (`VEHICLE_NOT_ACTIVE`), has an expired document (`VEHICLE_NOT_ROADWORTHY`) or is on another open dispatch (`VEHICLE_BUSY`). It sets the dispatch's vehicle text and driver. A vehicle on an open dispatch cannot be sent to the workshop.
- **Records:** fuel (litres and amount required), service, repair, tyre, accident (description required), other. The odometer can only go up (`ODOMETER_BACKWARDS`); a service resets the service interval. Costs paid by the company post Dr 6000 / Cr the payment account and need a payment method.
- **Van expenses:** fuel, toll and parking paid from a van's takings on a dispatch that has a vehicle are copied into the vehicle's history only. The van expense already booked the journal, so nothing is booked twice.
- **Report:** `GET /fmcg/fleet/report?start=&end=`: trips, delivered sales, cost by kind, km driven, cost per km, km per litre (needs two fuel records with odometer) and running cost as a percentage of sales.
- Not yet: drivers logging their own fuel from the phone, document file uploads, expiry notifications by email or SMS, a link from the vehicle to HR driver licences.

## Demand forecast

Code in `app/fmcg_forecast.py` + `app/fmcg_forecast_api.py` (`/fmcg/forecast`); screen **Demand forecast** (`/fmcg?tab=forecast`, `FmcgForecast.tsx`); no new tables (settings live in `tenants.document_numbering["fmcg_forecast_policy"]`). Managers and admins only.

- **Everything is an estimate** from delivered FMCG orders (net of returns, today left out) and is labelled so in the response (`meta.kind = "estimate"`), with the data period and a backtest.
- **Method:** daily demand = average of the look-back window (zero days count), blended 60/40 with the last 28 days when there are 56+ days; safety stock = z x standard deviation x square root of lead time; reorder point = demand x lead time + safety stock; suggested order = demand x (lead time + horizon) + safety stock - stock - open purchase orders not yet received. z comes from the service level (90/95/97/99).
- **Flags:** `stockout_risk` (stock at or below the reorder point), `overstock` (days of cover above the company limit), `dead` (stock but no sales in the window), `no_forecast` (fewer than 3 selling days). Each forecast row has days of cover, the date stock runs out, trend against the window average, promotion share and a confidence (low / medium / high from the number of selling days).
- **Accuracy:** `accuracy.error_pct` compares the method's prediction for the last 28 days (made from the days before) with what sold. Treat a high error as a reason not to trust the numbers.
- **Groups:** forecast quantity by category and by route (route history from the order's route).
- Lead time and service level are company-wide. Promotions, seasonality and new products are not modelled; a product that sold mostly on promotion shows its promotion share so a manager can judge.
- Not yet: per-product or per-supplier lead times, forecast by territory or outlet, creating purchase orders from the suggestions.

## Business overview and report centre

Code in `app/fmcg_dashboard.py`, `app/fmcg_reports.py` and `app/fmcg_reports_api.py`; screens **Business overview** and **Report centre** (`/fmcg?tab=command|centre`, `FmcgCentre.tsx`); no new tables. Managers and admins only (the plain **Dashboard** stays for every FMCG role).

- **`GET /fmcg/dashboard`:** sales (today, 7 days, month, year; delivered orders before tax, net of returns) with gross profit and margin; money (owed by outlets with ageing, late amount, owed to suppliers, purchases and credit sales this month); stock (products, units, valuation at cost, low and out of stock, batches by state, value at risk, products not sold in 90 days, fast movers, units lost or written off this month); operations (orders to load, on trucks, open dispatches, vans out, deliveries without proof, open recalls and complaints, inspections and promotions waiting, vehicle alerts, outlets, reps, vehicles, routes, outlets over their limit); charts (30-day sales, 12-month sales against purchases, by category, rep, route, outlet and product); and an attention list that links to the screen that fixes each item. Every figure is read live; the charts are plain bars with the numbers written beside them and a table of exact figures.
- **Report centre:** `GET /fmcg/reports/centre` lists 16 reports (sales by product / category / outlet / rep / route, who owes what, promotions, stock valuation, batches and expiry, forecast and suggested orders, van trips, vehicle costs, deliveries without proof, supplier quality, complaints, recalls). `GET /fmcg/reports/run?report=&start=&end=&format=json|csv` returns a table or a CSV (UTF-8 with BOM for Excel; cells starting with = + - or @ are prefixed so they never run as formulas). Periods are at most 366 days; tables are cut at 5,000 rows and say so.
- Sales reports use each product's current cost price for cost and margin. Forecast rows are estimates and are labelled as such.
- **Export formats:** CSV and the browser's print only. Excel (.xlsx) and PDF files are not generated.
- Not yet: filters by branch, warehouse, brand, distributor or salesperson on every report, saved or scheduled reports, an FMCG assistant that answers questions from these figures.

## Merchandising

Code in `app/fmcg_merch.py` + `app/fmcg_merch_api.py` (`/fmcg/merch`); screen **Shelf checks** (`/fmcg?tab=merch`, `FmcgMerch.tsx`); tables `fmcg_must_stock`, `fmcg_shelf_audits`, `fmcg_shelf_audit_lines`, `fmcg_competitor_prices` (migration `20261120_0220f`).

- **Must-stock list** (manager): products every outlet should carry and the fewest facings that count. Saving the list replaces it.
- **Shelf audit** (reps, managers): `POST /fmcg/merch/audits` for an outlet. Every must-stock product has to be answered (`MUST_STOCK_INCOMPLETE` otherwise); a product on the shelf needs 1+ facings and one that is not has none. Score = must-stock products on the shelf with at least their minimum facings, as a share of the list. Optional display check, notes, a shelf photo (PNG/JPEG, 800 KB), shelf prices, and a link to the rep's own visit at that outlet. A rep can only audit outlets in their territory (**403** `OUTSIDE_TERRITORY`) and sees only their own audits.
- **Competitor prices:** reps note a competitor product's shelf price against one of ours; managers read the list.
- **Shelf report** (manager, `GET /fmcg/merch/report`): audit reach (outlets audited out of active outlets), outlets weakest first, availability by product (where it was missing), audits and average score per rep, and our list and shelf prices against competitor average, low and high with a price index (our list price as a percentage of their average).
- Not yet: planograms with shelf positions, per-outlet must-stock lists by outlet class, photo comparison, merchandiser targets and incentives, GPS capture on the audit.

## Import shipments and landed cost

Code in `app/fmcg_landed.py` + `app/fmcg_landed_api.py` (`/fmcg/shipments`); screen **Import shipments** (`/fmcg?tab=imports`, `FmcgImports.tsx`); tables `fmcg_shipments`, `fmcg_shipment_lines`, `fmcg_shipment_costs` (migration `20261120_0221f`). Managers and admins only.

- **The goods are bought and received in Purchasing** (PO, goods receipt, supplier invoice), which already books Dr Inventory / Cr Accounts Payable. A shipment adds only what it cost to bring them in, so nothing is booked twice. Opening a shipment from a goods receipt fills its lines with the accepted quantities at the order price; one goods receipt can be on one live shipment.
- **Costs:** freight, insurance, customs duty, port, clearing, transport, other, each with a vendor and how it was paid (cash, bank, card, Mobile Money, cheque, or `payable` = owed to the supplier on Accounts Payable).
- **Allocate** (`POST /fmcg/shipments/{id}/allocate`, once): costs are spread over the lines by goods value or by units, exact to the cent (leftover cents go to the largest lines). For each product, the share that belongs to stock still on hand is added to its unit cost (`cost + share / units on hand`) and debited to Inventory; the share that belongs to units already sold is debited to Cost of Goods Sold. Credits are the cost's payment account or Accounts Payable. Before allocating, `GET` shows the exact preview.
- **After allocation** the shipment is frozen: no more lines or costs, no cancel, no undo. A mistake is corrected by a manual journal and a stock cost adjustment.
- Not yet: foreign-currency shipment lines (use the purchase invoice's currency), per-batch landed cost, shipment tracking statuses and documents, allocating one cost across several shipments, export documents and export orders.

## Manufacturing (optional)

Code in `app/fmcg_mfg.py` + `app/fmcg_mfg_api.py` (`/fmcg/manufacturing`); screen **Manufacturing** (`/fmcg?tab=manufacturing`, `FmcgMfg.tsx`); tables `fmcg_boms`, `fmcg_bom_lines`, `fmcg_production_orders`, `fmcg_production_materials`, `fmcg_production_trace`, `fmcg_production_overheads` (migration `20261120_0222f`). Managers and admins only. **Off by default:** `PUT /fmcg/manufacturing/settings {enabled}` switches it on per company; every other route answers **409** `MODULE_OFF` until then.

- **Recipe (bill of materials):** a finished product, how many units one batch makes, optional shelf life, and materials per batch with an allowed wastage percentage. A product cannot be its own material or listed twice. A recipe can be edited only until a production order uses it (`RECIPE_IN_USE`); then make a new one or switch it off.
- **Production order:** plan (units, date) -> **start** (refused with the shortfall list if materials are short, `MATERIALS_SHORT`; `GET .../check` shows it first) -> **complete** or cancel (reason).
- **Completing**, in one transaction: each material is taken out first-expiry-first-out (the batches used are saved for tracing); the finished product is received as a new batch (given or order-number batch, expiry given or from the shelf life, optionally held for quality control); unit cost = (materials at their cost price + overheads) / units made, and the product's cost becomes the weighted average of what was in stock and the new batch; overheads (labour, power, packaging, transport, other) are booked Dr Inventory / Cr cash, bank or Accounts Payable. Materials move inside Inventory so they need no journal. A failed completion changes nothing.
- **Wastage:** actual material used can be entered per material. Extra beyond the recipe stays in the cost and is reported as wastage cost and percentage against the recipe; yield and unit cost per order are in `GET /fmcg/manufacturing/report`.
- Not yet: multi-level recipes (a material that is itself made), co-products and by-products, work in progress between start and finish, machine and labour scheduling, partial completion of one order.

## More staff roles

Roles `fmcg_storekeeper` (Storekeeper), `fmcg_quality` (Quality Control Officer) and `fmcg_fleet` (Fleet Manager) are given in Users like the other FMCG roles and only in FMCG companies. Each is limited by `fmcg_orders.job` to its own areas, mirrored for menus by `FMCG_ROLE_HREFS`:

| Role | Can do | Cannot do |
| --- | --- | --- |
| Storekeeper | warehouse zones, bins, put-away, moves, counts, pick lists; see batches; stock levels and adjustments in Inventory | hold, write off or recall batches; quality; fleet; money screens |
| Quality Control Officer | inspections, supplier quality, complaints (including closing them); see batches; hold and release batches | write off or recall batches; warehouse; fleet; money screens |
| Fleet Manager | vehicles, documents, fuel and repair records, running costs, putting a vehicle on a dispatch | open or settle dispatches; batches; warehouse; quality; money screens |

Batch routes are split into `batches_read`, `batches_hold` and `batches` (write-off, recalls, policy). Managers and admins can do everything.

## FMCG assistant

Code in `app/fmcg_assistant.py` + `app/fmcg_assistant_api.py` (`POST /fmcg/assistant/ask`, `GET /fmcg/assistant/examples`); screen **Ask the assistant** (`/fmcg?tab=assistant`, `FmcgAssistant.tsx`). Managers and admins only.

- **It is not a language model.** A question is matched to a fixed set of questions (sales, profit by product, expiring stock, what to reorder, who owes money, top salesperson / route / outlets, stock not selling for 90 days, too much stock, van performance, stock valuation, delivery and vehicle cost, products likely to run out), answered by the same code as the dashboard and reports. It cannot invent a figure and answers anything else with the list of questions it knows.
- Each answer carries the figures, the period (it understands today, yesterday, this week, this month, last month, this year, last N days, and says when it defaulted to the last 30 days), the source, a link to the screen, and `kind`: `actual` or `estimate`. Forecast answers are always `estimate` and say so in the text.
- **Read only:** it never posts, approves or changes anything, and a request to do so is not answered.
- Not yet: questions about distributors, warehouses or territories by name, follow-up questions that remember the last answer, free-text reports, and a language-model mode through the shared AI provider.

## Report exports and filters

`GET /fmcg/reports/run?report=&format=json|csv|xlsx|pdf` (`app/fmcg_exports.py`).

- **Excel:** one sheet, bold header, frozen header row, column widths, money and number formats. Text beginning with = + - or @ is stored as text, never a formula.
- **PDF:** no extra library; landscape A4, as many pages as needed, header repeated on every page, "Page x of y". Courier font so columns line up; long cells are cut with "..." (the full text is in Excel or CSV) and characters outside Latin-1 print as ?.
- **Filters:** each report lists the filters it accepts in `GET /fmcg/reports/centre` (`filters`): product, category, brand, outlet, route, territory, sales rep, supplier, vehicle, status. A filter that does not apply to a report is refused with **422**, never silently ignored. The filters used are written at the top of the CSV, Excel and PDF. Names in that line are looked up for the caller's company only.
- Not yet: filters by branch, warehouse or distributor on every report, scheduled or emailed reports.

## Distributors

Code in `app/fmcg_distributors.py` + `app/fmcg_distributors_api.py` (`/fmcg/distributors`); screen **Distributors** (`/fmcg?tab=distributors`); table `fmcg_distributors` (migration `20261120_0223f`). Managers and admins only.

- A distributor is an ordinary outlet (orders, credit limit, payment terms and balance work as before) with a profile: kind (distributor, wholesaler, key account, supermarket), **price off list** (0-50%, applied to every product for that outlet before any promotion, and visible as the order line's unit price), a monthly sales target and an optional territory. A switched-off profile gives no discount.
- **Statement** (`GET .../statement?start=&end=`): delivered orders as debits, payments and returns as credits, with opening, running and closing balance worked back from the outlet's current balance, so any past period reconciles.
- **Performance** (`GET .../performance`, `GET .../ranking`): net sales, returns and return rate, gross profit and margin, collections against deliveries, what is owed and what is late, growth against the equal period before, target attainment (monthly target scaled to the period) and top products. Flags: behind target (under 70%), sales falling (down 20% or more), paying late (30% or more of what they owe is overdue), over credit limit, no orders. The ranking lists those needing attention first, and the assistant answers "Which distributors are performing poorly?" from it.
- Not yet: stock held at a distributor, distributor-specific price lists per product, distributor portal.

## Alerts

Code in `app/fmcg_alerts.py` + `app/fmcg_alerts_api.py`; table `fmcg_alert_log` (migration `20261120_0224f`); runs from the existing `scan_batch_expiry` Celery job (FMCG companies get this instead of the generic 30-day scan, so restart the worker after deploying), or on demand with `POST /fmcg/alerts/scan`.

- **Batches:** alerted when they first fall inside one of the company's warning days (default 90, 60, 30, 14, 7), again at each tighter stage, and once when expired. Each stage is sent once only (`fmcg_alert_log`), even if the notification was read or deleted. Empty batches are ignored.
- **Vehicles:** insurance, roadworthy and licence at 30, 14 and 7 days, then expired. Not-recorded documents and retired vehicles are ignored. New notification category `fleet_document`.
- **Who:** batch alerts go to company admins, the distribution manager, storekeepers and quality officers; vehicle alerts to company admins, the distribution manager and fleet managers. Email goes to everyone with email on for that category; **SMS goes only to people who switched SMS on for that category in Notifications and have a phone number**. Nothing is sent to reps or drivers.
- Not yet: a digest instead of one message per batch, alerts for credit limits and failed syncs, WhatsApp.

## Offline sync (field screens)

Code in `app/fmcg_offline.py` + `app/fmcg_offline_api.py` (`POST /fmcg/offline/sync`, `GET /fmcg/offline/log`), `frontend/lib/fmcgOffline.ts`, `frontend/components/FmcgOfflineBar.tsx`; table `fmcg_offline_refs` (migration `20261120_0225f`).

- **Covers:** shelf audits and competitor prices (Shelf checks), complaints and proof of delivery (Quality screens). A screen tries to save live; if the network is down it keeps the item on the device and says so. Other screens (selling, van, warehouse, quality decisions) still need a connection.
- **Safe retry:** each item has a reference the device makes up. The server saves a reference once; sending it again returns the first result as `duplicate`. Up to 50 per request, each in its own savepoint, so one refusal never blocks the rest. A refused item is returned with the reason, stays on the device marked failed, and can be sent again (retried) or discarded.
- **Same rules as live:** role, territory, validation, and a proof needs the order to be delivered already. The time the item was really taken is kept on the record. Items older than 72 hours or dated in the future are refused.
- **Clear about what is and is not safe:** the queue is in IndexedDB in this browser on this device. It survives closing the tab and restarting, but clearing site data, private browsing or another browser loses what was not yet sent, and the screen says so. 40 MB of unsent work per device is the limit. The service worker caches `/fmcg` so the app can open offline after a first visit.
- Not yet: offline selling and deliveries, background sync when the app is closed, taking a signature when the page was never opened online.

## Known limit

Retail `/sales` routes still answer for an FMCG company, because schemes also apply there and older tests use them. The menu no longer shows them.

## Demo

`PYTHONPATH=. python scripts/seed_fmcg_demo.py` creates `demo-fmcg-rec` (Northern Star Distributors; owner, rep and driver logins). It refuses to run in production.

## Live staff map (21 Nov 2026: `fmcg_tracking.py`, screen `/fmcg?tab=livemap`)

FMCG companies only. Shows where reps and drivers were last seen, with the day's path, distance and stops.

- **Not real-time GPS.** A web page reads the phone's position only while the ERP is open on screen. The screen is kept awake while sharing; if the phone still sleeps or the app closes, the map shows "last seen N min ago". Background tracking would need a native app.
- **Privacy rules (enforced on the server):** HR or an admin switches sharing on per person (`PUT /fmcg/tracking/people/{id}`); the person must accept a notice and sees a permanent banner; positions are refused unless the person is **clocked in** (HR clock, matched by login email); no one else is ever read.
- **Who sees whom:** company admin, HR manager and the distribution manager see everyone. Anyone else sees only the people who report to them in HR (the employee's manager link, transitive); a person out of scope gets 404, a manager with no reports gets 403.
- **Audit and retention:** every time a manager opens someone's day it is written to the audit log (`fmcg_tracking_trail_viewed`); switching on/off and notice acceptance are audited. Points older than 30 days are deleted by the daily FMCG scan (`scan_batch_expiry`; restart celery worker/beat after pull). A deleted user's points go with them. Tables `fmcg_track_state`, `fmcg_track_pings` are in backup specs.
- **Phone:** `components/StaffLocationSharer.tsx` (mounted in the Shell for FMCG): sends every 30 s or after moving 50 m, queues points offline, batches of up to 100; fixes worse than 200 m accuracy, future or over-12-hour-old points are dropped; duplicates ignored.
- **Map:** `components/TileMap.tsx`, OpenStreetMap tiles (no map library). A busy company should use its own tile provider (`tileUrl`).
- Migration `20261121_0228f`. **The privacy policy text (`legalDefaults.ts`) should disclose staff location tracking; that is the owner's legal wording to change.**
