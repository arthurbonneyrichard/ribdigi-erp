# Restaurant front-of-house split

**Decided 30 October 2026 (owner):** retail, hotel and restaurant stay isolated. Restaurant front of house gets its own tables and its own screens. The back office (ingredient stock, purchasing, accounting journals, tax, reports) stays the shared engine, kept per company by `tenant_id`.

## Today (before the split)

| Area | Restaurant uses | Shared with retail? |
| --- | --- | --- |
| Tables, orders, kitchen, recipes, modifiers, bookings | `restaurant_*` (11 tables), `/restaurant` page | No |
| Walk-up till sale | `transactions` (`tx_type=pos_sale`), `/pos/sales`, retail `/pos` page | **Yes** |
| Till shift, drawer | `pos_sessions`, cash movements, `/pos/sessions/*` | **Yes** |
| Till return | `sales_returns` / `sales_return_items`, `/pos/sales/{id}/returns` | **Yes** |
| Bills list, customers | retail `/sales`, `/customers` pages | **Yes** (screens) |
| Menu items / ingredients | `products`, `stock_movements`, `warehouse_stock` | Engine (kept) |
| Journals, tax, reports | `journal_entries`, report services with restaurant branches | Engine (kept) |

## Target

| Area | New home |
| --- | --- |
| Till shifts | `restaurant_till_shifts` (+ `restaurant_till_cash_moves`) |
| Till receipts | `restaurant_till_receipts` (+ `restaurant_till_receipt_lines`, `restaurant_till_payments`) |
| Till returns | `restaurant_till_returns` (+ `restaurant_till_return_lines`) |
| API | `/restaurant/till/*` (shifts, sale, receipts, returns, print). `/pos/*` refuses a restaurant company (403). |
| Screens | `/restaurant/till`, `/restaurant/bills`, `/restaurant/guests`. Sidebar no longer links `/pos`, `/sales`, `/customers`. Retail `/pos` page loses every `restaurantTill` branch. |
| Back office | Unchanged engine. Restaurant stock moves, journals and tax keep using the shared services, called from the restaurant till service. Report branches read the new restaurant tables instead of `transactions` / `sales_returns`. |

## Progress

- **30 Oct, phase 1 done** (`fdf5bf8ae8`): restaurant till tables and migration.
- **30 Oct, till screen done** (`8ccaa65990`): `/restaurant/till` is its own easy screen with its own look (brand greens on a light mist background, serif headings, docket ticket; amber only marks reserved tables and dishes cooking; none of the retail `tpos` styles). Every sale is a restaurant order: dine-in picks a table, takeaway and delivery take a name, phone and address; dishes get extras and a kitchen note; Send to kitchen, Open bills, Pay (cash with quick amounts and change, card, Mobile Money, wallet). It calls only `/restaurant/*`, so walk-up sales no longer write retail `transactions`. Restaurant menus no longer link the retail `/pos`.
- **Design change:** because the till rings restaurant orders, the separate `restaurant_till_receipts` / `_lines` / `_payments` tables are not needed for new sales. They stay only as the landing place for old restaurant rows moved out of retail `transactions` in phase 4, or are dropped then if that move goes into `restaurant_orders`. Shifts and cash moves (`restaurant_till_shifts`, `restaurant_till_cash_moves`) are still to be wired to the till.

## Phases (one commit each; full CI green before the next)

1. **Tables + migration.** New models and Alembic revision. Backfill copies a restaurant company's existing `pos_sessions`, `transactions (pos_sale)` and till `sales_returns` into the new tables, keeping ids so journals and stock movements still point at the same reference ids. Originals are left in place, marked, until phase 4.
2. **Restaurant till API.** `/restaurant/till/*` on the new tables, calling the shared pricing, recipe stock-out, journal and receipt-print services. Tests mirror the current restaurant till tests.
3. **Screens.** `/restaurant/till`, `/restaurant/bills`, `/restaurant/guests`; sidebar switched; restaurant branches removed from retail `/pos`.
4. **Engine reads + cut-over.** Dashboard, reports, tax and accounting restaurant branches read the new tables. `/pos/*` and retail `/sales` refuse restaurant companies. Backfilled originals removed from the shared tables.
5. **Readiness pass.** Signed-in walk on a disposable restaurant company (sale, split tender, return, shift close, reports, tax, journals). Readiness report updated.

Hotel follows the same pattern afterwards (its shop till also uses `/pos`).
