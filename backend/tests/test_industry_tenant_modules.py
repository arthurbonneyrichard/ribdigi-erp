"""Industry-based module entitlements, /me payload, API isolation, shared modules."""

from __future__ import annotations

from app.packages import (
    canonicalize_industry,
    industry_allows_module,
    package_modules,
    resolve_enabled_modules,
)
from app.rbac import has_permission
from tests.conftest import auth_headers, set_tenant_industry


def test_canonicalize_industry_aliases():
    assert canonicalize_industry("Hospitality") == "hotel"
    assert canonicalize_industry("supermarket") is None
    assert canonicalize_industry("retail") == "retail"
    assert canonicalize_industry("not-a-real-industry") is None
    assert canonicalize_industry("") is None
    assert canonicalize_industry(None) is None


def test_industry_allows_module_unknown_does_not_grant_verticals():
    assert industry_allows_module(None, "hotel") is False
    assert industry_allows_module("garbage", "hotel") is False
    assert industry_allows_module("retail", "hotel") is False
    assert industry_allows_module("hotel", "hotel") is True
    assert industry_allows_module("hotel", "inventory") is True
    assert industry_allows_module("mart", "inventory") is True
    assert industry_allows_module("hotel", "inventory") is True
    assert industry_allows_module("fmcg", "fmcg") is False
    assert industry_allows_module("hotel", "fmcg") is False
    assert has_permission("hotel_manager", "purchasing", "write")
    assert has_permission("hotel_manager", "inventory", "read")
    assert has_permission("hotel_manager", "company", "read")
    assert has_permission("company_admin", "company", "read")
    assert has_permission("hotel_housekeeping", "inventory", "read")
    assert not has_permission("hotel_front_desk", "inventory", "read")
    assert not has_permission("hotel_front_desk", "company", "read")


def test_trial_package_includes_verticals_but_resolve_filters():
    assert "hotel" in package_modules("trial")
    assert "fmcg" in package_modules("trial")

    class T:
        package_code = "trial"
        enabled_modules = None
        industry = "retail"

    retail = resolve_enabled_modules(T())
    assert "hotel" not in retail
    assert "fmcg" not in retail
    T.industry = "hotel"
    hotel = resolve_enabled_modules(T())
    assert "hotel" in hotel
    assert "fmcg" not in hotel
    T.industry = "hospitality"
    assert "hotel" in resolve_enabled_modules(T())


async def test_retail_admin_me_and_hotel_api_denied(client):
    ac, _seed = client
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    me = await ac.get("/api/v1/me", headers=admin)
    assert me.status_code == 200, me.text
    body = me.json()["data"]
    assert body["industry"] == "retail"
    assert body["industry_valid"] is True
    assert "hotel" not in body["enabled_modules"]
    assert "inventory" in body["enabled_modules"]
    assert "accounting" in body["enabled_modules"]

    denied = await ac.get("/api/v1/hotel/rooms", headers=admin)
    assert denied.status_code == 403, denied.text
    detail = denied.json().get("detail") or {}
    if isinstance(detail, dict):
        assert detail.get("code") == "INDUSTRY_MODULE_DISABLED"

    fmcg_denied = await ac.get("/api/v1/fmcg/schemes", headers=admin)
    assert fmcg_denied.status_code == 403, fmcg_denied.text


async def test_hotel_tenant_hotel_api_and_isolation(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    cashier = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    beta = await auth_headers(ac, email="cashier@beta.example.com", tenant_slug="beta")

    me = await ac.get("/api/v1/me", headers=admin)
    assert me.status_code == 200, me.text
    body = me.json()["data"]
    assert body["industry"] == "hotel"
    assert "hotel" in body["enabled_modules"]
    assert "fmcg" not in body["enabled_modules"]

    rooms = await ac.get("/api/v1/hotel/rooms", headers=admin)
    assert rooms.status_code == 200, rooms.text

    fmcg = await ac.get("/api/v1/fmcg/schemes", headers=admin)
    assert fmcg.status_code == 403, fmcg.text

    cashier_hotel = await ac.get("/api/v1/hotel/rooms", headers=cashier)
    assert cashier_hotel.status_code == 403, cashier_hotel.text

    beta_me = await ac.get("/api/v1/me", headers=beta)
    assert beta_me.json()["data"]["industry"] == "retail"
    beta_hotel = await ac.get("/api/v1/hotel/rooms", headers=beta)
    assert beta_hotel.status_code == 403, beta_hotel.text

    created = await ac.post(
        "/api/v1/hotel/rooms",
        headers=admin,
        json={"code": "101", "name": "Queen", "room_type": "standard", "rate_amount": 120},
    )
    assert created.status_code in {200, 201}, created.text
    listed = await ac.get("/api/v1/hotel/rooms", headers=admin)
    ids = {row["id"] for row in listed.json()["data"]}
    assert created.json()["data"]["id"] in ids

    dashboard = await ac.get("/api/v1/dashboard", headers=admin)
    assert dashboard.status_code == 200, dashboard.text


async def test_invalid_industry_does_not_grant_verticals(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "not-a-real-industry")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    me = await ac.get("/api/v1/me", headers=admin)
    assert me.status_code == 200, me.text
    body = me.json()["data"]
    assert body["industry_valid"] is False
    assert "hotel" not in (body.get("enabled_modules") or [])
    denied = await ac.get("/api/v1/hotel/rooms", headers=admin)
    assert denied.status_code == 403, denied.text


def test_hotel_sidebar_omits_unrelated_industry_features():
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    nav = (root / "frontend/lib/tenantNav.ts").read_text(encoding="utf-8")
    shell = (root / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    stores = (root / "frontend/app/(dashboard)/stores/page.tsx").read_text(encoding="utf-8")
    users = (root / "frontend/app/(dashboard)/users/page.tsx").read_text(encoding="utf-8")
    departments = (root / "frontend/app/(dashboard)/departments/page.tsx").read_text(encoding="utf-8")
    pos = (root / "frontend/app/(dashboard)/pos/page.tsx").read_text(encoding="utf-8")
    shift = (root / "frontend/lib/cashierShift.ts").read_text(encoding="utf-8")
    assert "if (hotel && !startShift)" in shift
    assert "const hotel = normalizeIndustry(data?.industry) === 'hotel'" in shift
    # A restaurant shift is the restaurant till's own, never a retail POS session.
    assert "'/restaurant/till/shift/open'" in shift
    assert "HOTEL_OMIT_NAV_GROUP_IDS" in nav
    assert "'inventory'" in nav and "'sales'" in nav and "'purchases'" in nav
    assert "'stores'" in nav
    assert "isHotelIndustry" in nav
    assert "'finance'" in nav and "'people'" in nav
    assert "Hostel" not in nav and "hostel" not in nav.lower()
    hotel_start = nav.find("export const HOTEL_NAV_ITEMS")
    hotel_end = nav.find("export const FMCG_NAV_ITEMS")
    hotel_block = nav[hotel_start:hotel_end]
    assert hotel_start >= 0 and hotel_end > hotel_start
    assert "Pharmacy" not in hotel_block
    assert "PHARMACY_NAV_ITEMS" not in nav
    assert "label: 'Pharmacy'" not in nav
    assert "'/pharmacy'" not in nav and '"/pharmacy"' not in nav
    assert "['POS'" not in nav and '["POS"' not in nav
    assert "['Shop till', '/hotel/shop', 'hotel']" in nav
    assert "['Shop till', '/pos'" not in nav
    assert "['Rate plans', '/hotel?tab=rooms#rate-plans', 'hotel']" in nav
    assert "['Guest requests', '/hotel?tab=front-desk#guest-requests', 'hotel']" in nav
    assert "['Lost and found', '/hotel?tab=housekeeping#lost-found', 'hotel']" in nav
    assert "['Group stays', '/hotel?tab=reservations#group-stay', 'hotel']" in nav
    assert "['Online booking', '/hotel?tab=reservations#online-booking', 'hotel']" in nav
    assert "['Night audit', '/hotel?tab=cashier#night-audit', 'hotel']" in nav
    assert "['Discount codes', '/sales?tab=coupons', 'sales']" in nav
    assert "['Gift cards', '/sales?tab=giftcards', 'sales']" in hotel_block
    assert "'/gift-cards'" not in hotel_block
    assert "['Lots', '/inventory?tab=batches', 'inventory']" in nav
    assert "['Supplier bills', '/purchasing?tab=invoices', 'purchasing']" in nav
    assert "['Purchase returns', '/purchasing?tab=returns', 'purchasing']" in nav
    assert "['Hotel Dashboard', '/hotel', 'hotel']" in nav or '["Hotel Dashboard", "/hotel", "hotel"]' in nav
    assert "['Company profile', '/company', 'company']" in nav or '["Company profile", "/company", "company"]' in nav
    assert "Events and Banquets" in nav
    assert "HOTEL_INVENTORY_PROCUREMENT_CHILDREN" in nav
    assert "Supplies" in nav
    assert "Low supplies" in nav
    assert "/inventory?tab=products" in nav
    assert "/inventory?tab=lowstock" in nav
    assert "/inventory?tab=adjust" in nav
    assert "/purchasing?tab=orders" in nav
    assert "/purchasing?tab=grn" in nav
    assert "/purchasing?tab=suppliers" in nav
    assert "/purchasing?tab=history" in nav
    assert "Retail management" not in nav
    assert "hotel-inventory" in nav
    assert "id: 'hotel'" in nav or 'id: "hotel"' in nav
    assert "from '../lib/tenantNav'" in shell
    assert "groupedTenantNav(TENANT_NAV_GROUPS, visible, industry, multiStore)" in shell
    assert "HOTEL_NAV_ITEMS" in shell
    assert "HOTEL_INVENTORY_PROCUREMENT_CHILDREN" in shell
    assert "hotel-inventory" in shell
    assert "isHotelIndustry(industry) && permModule === 'stores'" in shell
    assert "StoreSwitcher visible={!isHotelIndustry(industry)}" in shell
    assert "ALWAYS_LIST_NAV_GROUP_IDS" in nav
    assert "PEOPLE_NAV_ITEMS" in nav
    assert "['Branch', '/stores#branches', 'stores']" in nav
    assert "['Store', '/stores#stores', 'stores']" in nav
    assert "id: 'people'" in shell
    assert "label: 'User Management'" in shell
    assert "nav-group-static" in shell
    assert "ALWAYS_LIST_NAV_GROUP_IDS.has(group.id)" in shell
    assert "{ id: 'stores'" not in shell
    assert 'id="branches"' in stores
    assert 'id="stores"' in stores
    assert "router.replace('/hotel')" in stores
    assert "isHotelIndustry" in stores
    assert "hideStoreUx" in users
    assert "hideStorePicker" in pos
    sales = (root / "frontend/app/(dashboard)/sales/page.tsx").read_text(encoding="utf-8")
    customers = (root / "frontend/app/(dashboard)/customers/page.tsx").read_text(encoding="utf-8")
    purchasing = (root / "frontend/app/(dashboard)/purchasing/page.tsx").read_text(encoding="utf-8")
    expenses = (root / "frontend/app/(dashboard)/expenses/page.tsx").read_text(encoding="utf-8")
    accounting = (root / "frontend/app/(dashboard)/accounting/page.tsx").read_text(encoding="utf-8")
    reports = (root / "frontend/app/(dashboard)/reports/page.tsx").read_text(encoding="utf-8")
    credit = (root / "frontend/app/(dashboard)/credit/page.tsx").read_text(encoding="utf-8")
    notifications = (root / "frontend/app/(dashboard)/notifications/page.tsx").read_text(encoding="utf-8")
    printers = (root / "frontend/app/(dashboard)/printers/page.tsx").read_text(encoding="utf-8")
    tax = (root / "frontend/app/(dashboard)/tax/page.tsx").read_text(encoding="utf-8")
    billing = (root / "frontend/app/(dashboard)/billing/page.tsx").read_text(encoding="utf-8")
    company = (root / "frontend/app/(dashboard)/company/page.tsx").read_text(encoding="utf-8")
    audit = (root / "frontend/app/(dashboard)/audit/page.tsx").read_text(encoding="utf-8")
    backup = (root / "frontend/app/(dashboard)/backup/page.tsx").read_text(encoding="utf-8")
    assert "Checkout invoices from guest folios land here" in sales
    assert "Bills from the restaurant till land here. Table orders stay on the restaurant desk." in sales
    assert "hotelOps ? 'Supply' : restaurantOps ? 'Menu item' : 'Product'" in sales
    assert "hotelOps ? 'Supplies' : restaurantOps ? 'Menu items' : 'Products'" in sales
    assert "Choose a supply and a quantity first" in sales
    assert "Choose a menu item and a quantity first" in sales
    assert "Choose a product and a quantity first" in sales
    assert "Walk-in guest" in sales
    assert "Walk-in diner" in sales
    assert "Walk-in'" in sales
    assert "No bills yet. Create a bill when you are ready to charge the guest." in sales
    assert "No invoices yet. Create an invoice when you are ready to bill the customer." in sales
    assert "Put the menu item back" in sales
    assert "Put back on hand" in sales
    assert "Restock" in sales
    assert "Restaurant till bills and checkout invoices show here." in sales
    assert "rest-bill-table" in sales
    assert "rest-return-table" in sales
    assert "restaurantOps ? 'Return' : 'Number'" in sales
    assert "No returns yet. Create a return from a posted bill." in sales
    assert "No returns yet. Create a return from a posted invoice." in sales
    assert "restaurantOps ? 5 : 7" in sales
    assert "restaurantOps ? 'Bill' : 'Number'" in sales
    assert "restaurantOps ? 'Create bill' : 'Create invoice'" in sales
    assert "Checkout invoices and shop till sales show here." in sales
    assert "Completed invoices and register sales show here." in sales
    ai = (root / "frontend/app/(dashboard)/ai/page.tsx").read_text(encoding="utf-8")
    assert "Supply predictions" in ai
    assert "Ingredient predictions" in ai
    assert "Inventory predictions" in ai
    assert "days on hand" in ai
    assert "days of ingredients left" in ai
    assert "days of stock left" in ai
    inventory = (root / "frontend/app/(dashboard)/inventory/page.tsx").read_text(encoding="utf-8")
    assert "products: 'Ingredients'" in inventory
    assert "hotelOps ? 'Supply' : restaurantOps ? 'Ingredient' : 'Product'" in inventory
    assert "Ingredient list" in inventory
    assert "Supply list" in inventory
    assert 'aria-label="Create restaurant menu station"' in inventory
    assert 'aria-label="Edit restaurant menu station"' in inventory
    assert "productStation === 'kitchen' || productStation === 'bar'" in inventory
    assert "clear_prep_station: true" in inventory
    assert 'data-label="On hand"' in inventory
    assert "restaurantOps ? 8 : 5" in inventory
    assert "p.prep_station === 'bar' ? 'Bar'" in inventory
    assert "rest-ing-table" in inventory
    assert "Ingredients running low and due for reordering" in inventory
    assert "Products running low and due for reordering" in inventory
    assert "stockStatusText(String(r.stock_status_label || r.stock_status || 'ok'), hotelOps, restaurantOps)" in inventory
    assert "restaurantOps ? 'On hand' : 'Qty'" in inventory
    assert "stockStatusText(apiText, hotel, restaurant)" in inventory
    assert "Pick a batch that belongs to this ingredient" in inventory
    assert "Pick a batch that belongs to this supply" in inventory
    assert "Pick a batch that belongs to this product" in inventory
    assert "No warehouse rows for this ingredient" in inventory
    assert "No location rows for this supply" in inventory
    assert "No warehouse rows for this product" in inventory
    assert "No lots yet for this ingredient." in inventory
    assert "No lots yet for this supply." in inventory
    assert "No lots yet for this product." in inventory
    assert "Selected ingredient only" in inventory
    assert "Selected supply only" in inventory
    assert "Selected product only" in inventory
    assert "Ingredient lines" in inventory
    assert "Supply lines" in inventory
    assert "Product lines" in inventory
    assert "No ingredient counts yet." in inventory
    assert "No supply counts yet." in inventory
    assert "No stock counts yet." in inventory
    assert "Start ingredient count" in inventory
    assert "Start supply count" in inventory
    assert "Start stock count" in inventory
    assert "Select a warehouse for opening ingredients" in inventory
    assert "Select a location for opening supplies" in inventory
    assert "Select a warehouse for opening stock" in inventory
    assert "No warehouse is available for this restaurant." in inventory
    assert "No location is available for this hotel." in inventory
    assert "No warehouse is available for this store" in inventory
    assert "Pick a warehouse to load ingredients" in inventory
    assert "Pick a location to load stock" in inventory
    assert "Company ingredients (no warehouse)" in inventory
    assert "Company stock (no location)" in inventory
    assert "Post ingredients out" in inventory
    assert "Post supplies out" in inventory
    assert "Post stock out" in inventory
    assert "No opening ingredients posted yet." in inventory
    assert "No opening supplies posted yet." in inventory
    assert "No opening stock posted yet." in inventory
    assert "No ingredient history yet." in inventory
    assert "No supply history yet." in inventory
    assert "No stock history yet." in inventory
    assert "Adjust ingredients" in inventory
    assert "Adjust supplies" in inventory
    assert "Adjust stock" in inventory
    assert "Receive ingredients into this warehouse to add the first row." in inventory
    assert "Receive supplies into this location to add the first row." in inventory
    assert "Receive stock into this location to add the first stock row." in inventory
    assert "No ingredients yet. Add an ingredient to cook from or a menu item to sell." in inventory
    assert "No supplies yet. Add linen, toiletries, food, drink, or cleaning supplies." in inventory
    assert "No products yet. Add a product to sell it and track stock." in inventory
    assert "Product List" in inventory
    assert "Search, filter, and add ingredients for this restaurant." in inventory
    assert "Search, filter, and add linen, toiletries, food, drink, and cleaning supplies." in inventory
    assert "Search, filter, and add products for this company." in inventory
    assert "lowstock: 'Low ingredients'" in inventory
    assert "products: 'Supplies'" in inventory
    assert "products: 'Products'" in inventory
    assert "Linen, toiletries, F&B and cleaning supplies use the same supply records as the rest of the hotel." in inventory
    purchasing = (root / "frontend/app/(dashboard)/purchasing/page.tsx").read_text(encoding="utf-8")
    assert "3 Receive stock" in purchasing
    assert "3 Receive supplies" in purchasing
    assert "3 Receive goods" in purchasing
    assert "stock received for recipe ingredients" in purchasing
    assert "hotelOps ? 'Supply' : restaurantOps ? 'Ingredient' : 'Product'" in purchasing
    assert "hotelOps ? 'Add supply' : restaurantOps ? 'Add ingredient' : 'Add product'" in purchasing
    assert "Add every supply for this supplier" in purchasing
    assert "Add every ingredient for this supplier" in purchasing
    assert "Add every product for this supplier" in purchasing
    assert "Choose a product first" in purchasing
    assert "rest-purch-table" in purchasing
    assert "restaurantOps ? 6 : 9" in purchasing
    assert "restaurantOps ? 6 : 13" in purchasing
    assert "restaurantOps ? 'Request' : 'Number'" in purchasing
    assert "restaurantOps ? 4 : 7" in purchasing
    assert "restaurantOps ? 5 : 9" in purchasing
    assert "restaurantOps ? 'Amount' : 'Amount / qty'" in purchasing
    assert "restaurantOps ? 4 : 6" in purchasing
    assert "Orders, stock receipts, supplier bills, and returns. This is not the reports summary." in purchasing
    assert "Orders, goods received, supplier bills, and returns — not the reports summary." in purchasing
    assert "No debit note" in purchasing
    assert "Receive stock first, then create a purchase return for that supplier." in purchasing
    assert "Create a purchase request when you need approval before buying ingredients." in purchasing
    assert "Create a purchase request when you need approval before an order." in purchasing
    assert "Add a purchase order for a supplier." in purchasing
    assert "goods received for hotel supplies" in purchasing
    assert "Receive a sent order to list the stock receipt here." in purchasing
    assert "Receive a sent order to list the delivery here." in purchasing
    assert "Receive a sent order to list the goods receipt here." in purchasing
    assert "restaurantOps ? 6 : 10" in purchasing
    assert "Rejected {rejected}" in purchasing
    assert "Receive stock (accept / reject)" in purchasing
    assert "Receive supplies (accept / reject)" in purchasing
    assert "Post GRN (accept / reject)" in purchasing
    assert "Bill from a receipt" in purchasing
    assert "Bill from a delivery" in purchasing
    assert "Bill from GRN" in purchasing
    assert "Draft only; ingredients and supplier bills stay unchanged." in purchasing
    assert "Draft only; supplies and supplier bills stay unchanged." in purchasing
    assert "Draft only; no stock/AP." in purchasing
    assert "['invoices', 'Bills']" in sales
    assert "Coupons and gift cards are codes, not a card charge." in sales
    assert "Guest profiles stay on Guests and CRM" in customers
    assert "Customers on restaurant bills" in customers
    assert "Your customers, used on quotes, orders and invoices." in customers
    assert "Add a customer to use them on restaurant bills" in customers
    assert "rest-cust-table" in customers
    assert "restaurantOps ? 'Customer' : 'Name'" in customers
    assert "<th>Loyalty</th>" in customers
    assert "hotelOps ? 'Walk-in guest' : restaurantOps ? 'Walk-in diner' : 'Walk-in'" in customers
    assert "(walk-in diner)" in customers
    assert "(walk-in guest)" in customers
    assert "(walk-in)" in customers
    assert "Hotel administration" in company
    assert "Restaurant administration" in company
    assert "Company administration" in company
    assert "Shop till offline hours" in company
    assert "Restaurant till offline hours" in company
    assert "Sign-out cash count" in company
    assert "Restaurant till sign-out" in company
    assert "if (hotel && key === 'pos') return 'Shop till';" in audit
    assert "if (restaurant && key === 'pos') return 'Restaurant till';" in audit
    assert "if (restaurant && key === 'inventory') return 'Ingredients';" in audit
    assert "pos: 'Point of sale'" in audit
    assert "if (hotel && key === 'product') return 'Supply';" in audit
    assert "if (restaurant && key === 'product') return 'Menu item';" in audit
    assert "rest-audit-table" in audit
    assert "restaurantOps ? 4 : 8" in audit
    assert "<th>Area</th>" in audit
    assert "<th>Record type</th>" in audit
    assert "<th>Network address</th>" in audit
    assert "<th>Stored away</th>" in audit
    assert "<th>What happened</th>" in audit
    assert "<th>Person</th>" in audit
    assert "No person" in audit
    assert "No address" in audit
    assert "No link" in audit
    assert "Still here" in audit
    assert "No activity matches these filters. Clear a code or widen the dates, then choose Apply filters." in audit
    assert "No records match these filters. Clear a code or widen the dates, then choose Apply filters." in audit
    assert "This overwrites matching supplies, sales, purchases, on-hand quantities and ledger records in this hotel." in backup
    assert "This overwrites matching ingredients, sales, purchases, on-hand quantities and ledger records in this restaurant." in backup
    assert "rest-backup-table" in backup
    assert "restaurantOps ? 4 : 5" in backup
    assert "<th>Backup</th>" in backup
    assert "<th>When</th>" in backup
    assert "<th>Note</th>" in backup
    assert "<th>Size</th>" in backup
    assert "No note" in backup
    assert "No backups yet. Add a note if you want one, then choose Create backup now." in backup
    assert "This overwrites matching product, sales, purchase, stock and ledger records in this company." in backup
    assert "goods received for hotel supplies" in purchasing
    assert "Hotel costs" in expenses
    assert "Restaurant costs" in expenses
    assert "rest-exp-table" in expenses
    assert "restaurantOps ? 'Cost' : 'Payee'" in expenses
    assert "restaurantOps ? 5 : 6" in expenses
    assert "No costs yet. Submit a cost when you are ready to record it." in expenses
    assert "No expenses yet. Fill in the form above and submit one." in expenses
    assert "rest-cat-table" in expenses
    assert "rest-cat-span" in expenses
    assert "restaurantOps ? 4 : 6" in expenses
    assert "<th>Category</th>" in expenses
    assert "<th>Code</th>" in expenses
    assert "<th>Name</th>" in expenses
    assert "<th>Active</th>" in expenses
    assert "No cost groups yet. Add a group when you are ready to sort costs." in expenses
    assert "Each group is a kind of cost. Set a monthly budget, then reports compare what you spent with that budget." in expenses
    assert "Set a monthly budget for each category. Reports compare spending with that budget." in expenses
    assert "rest-sched-table" in expenses
    assert "rest-sched-span" in expenses
    assert "restaurantOps ? 4 : 7" in expenses
    assert "<th>Schedule</th>" in expenses
    assert "<th>Payee</th>" in expenses
    assert "<th>How often</th>" in expenses
    assert "<th>Next date</th>" in expenses
    assert "No payee" in expenses
    assert "No repeating costs yet. Create a schedule when the same cost happens again." in expenses
    assert "No recurring schedules yet. Fill in the fields above and create a schedule." in expenses
    assert "rest-income-table" in expenses
    assert "restaurantOps ? 3 : 4" in expenses
    assert "<th>Receipt</th>" in expenses
    assert "<th>Description</th>" in expenses
    assert "<th>Payer</th>" in expenses
    assert "No payer" in expenses
    assert "No other money yet. Post it when the restaurant receives money that is not a bill." in expenses
    assert "No other income recorded. Enter a description and amount, then post income." in expenses
    assert "Money the restaurant received that is not a bill. It stays separate from a cost." in expenses
    assert "Money the company received that is not a sale. It is separate from an expense." in expenses
    assert "A reason is required before you skip the next date. It is kept with the schedule." in expenses
    assert "recurring_expense_skipped" in expenses
    assert "Submit an expense with the form below" in expenses
    assert "Guest folio payments stay on Billing until checkout" in accounting
    assert "Restaurant till bills, restaurant expenses, and supplier bills post here" in accounting
    assert "rest-acc-table" in accounting
    assert "restaurantOps ? 5 : 7" in accounting
    assert "No entries yet. Bills, costs, and supplier bills show here when they are posted." in accounting
    assert "No entries yet" in accounting
    assert "<th>Description</th>" in accounting
    assert "<th>Source</th>" in accounting
    assert "rest-cash-table" in accounting
    assert "<th>Account</th>" in accounting
    assert "<th>Code</th>" in accounting
    assert "<th>Name</th>" in accounting
    assert "<th>Bank</th>" in accounting
    assert "No bank details" in accounting
    assert "No cash or bank accounts yet. Add one when you are ready to record a payment." in accounting
    assert "rest-move-table" in accounting
    assert "restaurantOps ? 4 : 5" in accounting
    assert "<th>Movement</th>" in accounting
    assert "<th>Kind</th>" in accounting
    assert "<th>Reference</th>" in accounting
    assert "No reference" in accounting
    assert "No movements yet. Post a transfer, deposit, or withdrawal when you are ready." in accounting
    assert "No transfers for this filter" in accounting
    assert "rest-coa-table" in accounting
    assert "restaurantOps ? 5 : 9" in accounting
    assert "<th>Account</th>" in accounting
    assert "<th>Code</th>" in accounting
    assert "<th>Name</th>" in accounting
    assert "<th>Type</th>" in accounting
    assert "<th>Parent</th>" in accounting
    assert "<th>Liquid</th>" in accounting
    assert "<th>Active</th>" in accounting
    assert "Top level" in accounting
    assert "No accounts yet. Add an account when you are ready to group money." in accounting
    assert "No accounts for this filter" in accounting
    assert "rest-stmt-table" in accounting
    assert "restaurantOps ? 5 : 6" in accounting
    assert "<th>Statement</th>" in accounting
    assert "<th>Date</th>" in accounting
    assert "<th>Status</th>" in accounting
    assert "<th>Unmatched</th>" in accounting
    assert "<th>Left to match</th>" in accounting
    assert "No statements yet. Create a statement when you are ready to match the bank." in accounting
    assert "No statements for this filter" in accounting
    assert "rest-cheque-table" in accounting
    assert "restaurantOps ? 4 : 7" in accounting
    assert "<th>Cheque</th>" in accounting
    assert "<th>Number</th>" in accounting
    assert "<th>Dir</th>" in accounting
    assert "<th>Notes</th>" in accounting
    assert "No bank name" in accounting
    assert "No cheques yet. A cheque shows here after you record a customer or supplier payment by cheque." in accounting
    assert "No cheques — record a customer/supplier payment with method cheque" in accounting
    assert "A reason is required before you bounce or cancel a cheque. It is kept with the cheque." in accounting
    assert "POST .../bounce|cancel" in accounting
    assert "Sales, expenses and supplier bills post here automatically" in accounting
    assert "Cost of supplies" in accounting
    assert "Cost of ingredients" in accounting
    assert "Cost of goods" in accounting
    assert "Shop till sale" in accounting
    assert "Restaurant till sale" in accounting
    assert "pos_sale: 'POS sale'" in accounting
    assert "Occupancy and room revenue are on Hotel reports" in reports
    assert "Totals for this company" in reports
    assert "guest folio stays on Billing until checkout" in credit
    assert "Amounts still owed on restaurant bills" in credit
    assert "rest-credit-table" in credit
    assert "restaurantOps ? 'Not yet due' : 'Current'" in credit
    assert "No restaurant bills with a remaining balance." in credit
    assert "No customer invoices with a remaining balance." in credit
    assert "<th>1–30</th>" in credit
    assert "Choose the customer, check what they owe" in credit
    assert "hotelOps ? 'Supply' : restaurantOps ? 'Menu item' : 'Product'" in credit
    assert "Alerts for this hotel" in notifications
    assert "Things in your shop that need you" in notifications
    assert "label: 'POS'" in notifications
    assert "label: 'Stock'" in notifications
    notify = (root / "frontend/lib/notifyText.ts").read_text(encoding="utf-8")
    assert "shift_variance: 'Shop till'" in notify
    assert "low_stock: 'Supplies'" in notify
    assert "shift_variance: 'Till'" in notify
    assert "shift_variance: 'Restaurant till'" in notify
    assert "low_stock: 'Ingredients'" in notify
    assert "Alerts for this restaurant" in notifications
    assert "rest-alert-table" in notifications
    assert "restaurantOps ? 3 : 4" in notifications
    assert "<th>Alert</th>" in notifications
    assert "<th>When</th>" in notifications
    assert "<th>Type</th>" in notifications
    assert "<th>Action</th>" in notifications
    assert "rest-pref-table" in notifications
    assert "<th>Kind of alert</th>" in notifications
    assert "<th>In the app</th>" in notifications
    assert "<th>Email</th>" in notifications
    assert "<th>SMS</th>" in notifications
    assert "Hotel staff who can sign in" in users
    assert "Restaurant staff who can sign in" in users
    assert "rest-user-table" in users
    assert "<th>Person</th>" in users
    assert "<th>Sees</th>" in users
    assert "<th>Scope</th>" in users
    assert "<th>Department</th>" in users
    assert "className=\"user-manage-name\">Name" in users
    assert "className=\"user-manage-email\">Email" in users
    assert "No staff yet. Add a person with a name, email, password, and role." in users
    assert "No users yet. Add a person with a name, email, password, and role." in users
    assert "No staff for this filter. Choose All to see everyone in this restaurant." in users
    assert "No users for this filter. Choose All to see everyone in this company." in users
    assert "restaurantOps ? (r.is_active ? 'Active' : 'Not in use')" in users
    assert "r.is_active ? 'Active' : 'Inactive'" in users
    assert "See who can sign in, then add a person" in users
    assert "cashier: 'Shop cashier'" in users
    assert "cashier: 'Cashier (all service screens)'" in users
    assert "e.g. Night auditor" in users
    assert "e.g. Floor supervisor" in users
    assert "e.g. Shop supervisor" in users
    assert "rest-dept-table" in departments
    assert "restaurantOps ? (canWrite ? 3 : 2)" in departments
    assert "<th>Department</th>" in departments
    assert "<th>Status</th>" in departments
    assert "<th>Code</th>" in departments
    assert "<th>Name</th>" in departments
    assert "<th>Active</th>" in departments
    assert "No departments yet. Create one when you are ready to group staff." in departments
    assert "No departments for this filter. Choose All statuses to see every department." in departments
    assert "No departments match this filter." in departments
    assert "Departments in this restaurant. Each name must be unique. Assign staff to them in User Management." in departments
    assert "Departments in your company. Each name must be unique. Assign staff to them in User Management." in departments
    assert "Not in use" in departments
    assert "Inactive" in departments
    presence = (root / "frontend/components/CashierPresencePanel.tsx").read_text(encoding="utf-8")
    assert "No one is on the shop till." in presence
    assert "No one is on the restaurant till." in presence
    assert "No active cashiers." in presence
    assert "No POS signal" in presence
    assert "reservation confirmations, folio print, and guest receipts" in printers
    assert "Link a printer for the restaurant till" in printers
    assert "kitchen tickets, and bar tickets" in printers
    assert "Link a printer for the till" in printers
    assert "rest-print-table" in printers
    assert "restaurantPrint ? 4 : 6" in printers
    assert "<th>How it connects</th>" in printers
    assert "<th>Used for</th>" in printers
    assert "<th>Actions</th>" in printers
    assert "<th>Printer</th>" in printers
    assert "<th>Paper</th>" in printers
    assert "Not used for a job" in printers
    assert "A4 bill" in printers
    assert "A4 invoice" in printers
    assert "nights times the nightly rate" in tax
    assert "The default rate applies unless a menu item or bill line uses a different one" in tax
    assert "The default rate applies unless a product or line uses a different one" in tax
    assert "hotelOps ? 'Shop till' : restaurantOps ? 'Restaurant till' : 'Till'" in tax
    assert "rest-tax-table" in tax
    assert "<th>Rate</th>" in tax
    assert "<th>Percent</th>" in tax
    assert "<th>On the price</th>" in tax
    assert "<th>Name</th>" in tax
    assert "<th>Type</th>" in tax
    assert "<th>Mode</th>" in tax
    assert "<th>RC</th>" in tax
    assert "<th>Components</th>" in tax
    assert "<th>Default</th>" in tax
    assert "<th>Active</th>" in tax
    assert "Default rate" in tax
    assert "Not in use" in tax
    assert "No extra parts" in tax
    assert "Customer pays the tax" in tax
    assert "No tax rates yet. Add a rate when you are ready to charge tax on a bill." in tax
    assert "No rates for this filter. Choose All statuses to see every rate." in tax
    assert "Folio payments stay on Billing in Hotel until checkout" in billing
    assert "outside a restaurant bill" in billing
    assert "Record a payment you already received" in billing
    assert "Walk-up shop sales. Meals and drinks stay on the guest bill. Guest folio charges stay on Billing." in pos
    assert "Shop till" in pos
    assert "Start shop shift" in pos
    assert "Wait for your shift to open, then scan or search for a product." in pos
    assert "Point of Sale" in pos
    assert "restaurantTill ? 'Restaurant till'" in pos
    assert "const restaurantCompany = industryNow === 'restaurant'" in pos
    assert "tillIndustry && !hotelCompany && !restaurantCompany" in pos
    assert "Walk-up sales from this till. Table orders stay on the restaurant desk." in pos
    assert "Start restaurant shift" in pos
    assert "online && !restaurantTill ? <option value=\"gift_card\">Gift card</option> : null" in pos
    assert '<option value="credit">Credit</option>' in pos
    assert "online && !restaurantTill ? <option value=\"loyalty\">Loyalty points</option> : null" in pos
    assert "The restaurant till stays online. Connect, then take the payment." in pos
    assert "This till does not charge a card." in pos
    assert "Gift cards and loyalty stay on retail sales." in pos
    assert "The restaurant till stays online." in pos
    assert "A menu item with a recipe uses its ingredients." in pos
    assert "The ingredient cost is posted to cost of goods." in pos
    assert "<option value=\"gift_card\">Gift card</option>" in pos
    assert "<option value=\"loyalty\">Loyalty points</option>" in pos
    assert "restaurantTill ? 'Walk-in diner' : 'Walk-in'" in pos
    assert "Walk-in diner if none selected" in pos
    assert "Walk-in if none selected" in pos
    assert "No menu item for ${query} in the saved catalog" in pos
    assert "No product for ${query} in the saved catalog" in pos
    assert "is sold out at this store" in pos
    assert "is out of stock at this store" in pos
    assert "has no menu items to sell yet. Add menu items in Ingredients, then come back." in pos
    assert "has no products in stock to sell yet. Add products and their stock in Inventory, then come back." in pos
    assert "Scan or search, then tap a menu item to add it." in pos
    assert "Scan or search, then tap a product to add it." in pos
    assert "Add a menu item before charging" in pos
    assert "Add a product before charging" in pos
    assert "Show all menu items" in pos
    assert "Show all products" in pos
    assert "Till shift" in pos
    assert "Close till shift" in pos
    greet = (root / "frontend/components/DashboardGreeting.tsx").read_text(encoding="utf-8")
    assert "Good morning" in greet and "Good afternoon" in greet and "Good evening" in greet
    assert "dash-hero" in greet
    hotel = (root / "frontend/app/(dashboard)/hotel/page.tsx").read_text(encoding="utf-8")
    assert 'desk="Hotel dashboard"' in hotel
    restaurant = (root / "frontend/app/(dashboard)/restaurant/page.tsx").read_text(encoding="utf-8")
    assert 'desk="Restaurant dashboard"' in restaurant
    assert "restaurantDesk && tab === 'dashboard'" in restaurant
    assert "Kitchen and bar" in restaurant
    assert "Open a restaurant desk." in restaurant
    assert "No open orders." in restaurant
    assert "No tickets in the kitchen or at the bar." in restaurant
    assert "No operational alerts." in restaurant
    assert "Booking link is not saved." in restaurant
    assert "No restaurant shift is open." in restaurant
    assert 'aria-label="Restaurant operational alerts"' in restaurant
    assert 'aria-label="Restaurant quick desks"' in restaurant
    assert "Loading restaurant totals…" in restaurant
    assert "Sales today" in restaurant
    assert "Mark ${item.name} ready on ${row.order_number}" in restaurant
    assert "Start ${item.name} on ${row.order_number}" in restaurant
    assert "Start ${item.name} on ${row.order_number}" not in hotel
    assert "Table bills" in restaurant
    assert "Restaurant till" in restaurant
    assert "Table bills" not in hotel
    assert "Company dashboard profit uses the ingredient cost." in restaurant
    assert "A restaurant till return comes off company dashboard profit without the tax. Sales today keeps the tax." in restaurant
    assert "A completed restaurant bill includes its service charge in company dashboard profit." in restaurant
    assert "A restaurant till discount comes off company dashboard profit. Top dishes stay at the menu amount." in restaurant
    assert "A menu item with no recipe uses its own cost." in restaurant
    assert "A restaurant till return comes off Sales today." in restaurant
    assert "A restaurant till return comes off Sales today for the store on the original receipt." in restaurant
    assert "A restaurant till return comes off Sales today." not in hotel
    assert "A restaurant till return comes off Sales today for the store on the original receipt." not in hotel
    assert "Company dashboard profit uses the ingredient cost." not in hotel
    assert "A restaurant till return comes off company dashboard profit without the tax. Sales today keeps the tax." not in hotel
    assert "A completed restaurant bill includes its service charge in company dashboard profit." not in hotel
    assert "A restaurant till discount comes off company dashboard profit. Top dishes stay at the menu amount." not in hotel
    assert "More desks" not in restaurant
    assert "Open by tender" not in restaurant
    assert "Open by service" not in restaurant
    restaurant_settings = nav.split("id: 'restaurant-settings'", 1)[1].split("export const FMCG", 1)[0]
    assert "['AI Assistant', '/ai', 'ai']" in restaurant_settings
    hotel_settings = nav.split("id: 'hotel-settings'", 1)[1].split("export const RESTAURANT", 1)[0]
    assert "['AI Assistant', '/ai', 'ai']" in hotel_settings
    # Everything loads once; the 15 s refresh only fetches the live lists plus the open desk's extras.
    all_extras = restaurant.split("const ALL_EXTRAS = [", 1)[1].split("];", 1)[0]
    assert "'/restaurant/waste'" in all_extras and "'/restaurant/till/shift'" in all_extras
    assert "DESK_EXTRAS[tab]" in restaurant and "refresh(true)" in restaurant
    assert "document.hidden" in restaurant
    assert "/pos/sessions/current" not in restaurant
    assert "spoilage: 'Spoilage'" in restaurant
    assert "Walk-in or phone request" in restaurant
    assert 'aria-label="Save restaurant walk-in booking"' in restaurant
    assert "Save leftover booking ${row.booking_number}" in restaurant
    assert "Leftover booking notes ${row.booking_number}" in restaurant
    assert "/restaurant/bookings/${row.id}" in restaurant
    assert "This does not need a booking website and does not take a payment." in restaurant
    assert 'aria-label="Save restaurant booking link"' in restaurant
    assert 'aria-label="Restaurant booking website"' in restaurant
    assert "Saving the host does not move DNS" in restaurant
    assert " · Occupied" not in restaurant
    assert "1 menu item has no recipe." in restaurant
    assert "no recipe" in restaurant
    assert 'rd-kpis' in restaurant and 'Kitchen and bar' in restaurant
    assert "1 ticket is ready to serve." in restaurant
    assert "1 ingredient is low." in restaurant
    assert "Booking link for the website" in restaurant
    assert "Finish frees that table when no open order is using it." in restaurant
    assert "booking requests are waiting." in restaurant
    assert 'aria-label="Restaurant order table"' in restaurant
    tables_desk = restaurant.split("tab === 'tables'", 1)[1].split("tab === 'booking'", 1)[0]
    assert "orderWord(row.status)" in tables_desk
    assert "({row.status})" not in tables_desk
    assert "No tables yet." in tables_desk
    assert "1 seat" in tables_desk
    assert "seats" in tables_desk
    assert 'aria-label="Restaurant floor"' in tables_desk
    assert "rest-floor" in tables_desk
    assert "rest-floor-fields" in tables_desk
    floor_fields = tables_desk.split('className="rest-floor-fields', 1)[1].split('className="rest-floor-actions', 1)[0]
    assert "<span>Code</span>" in floor_fields
    assert "<span>Name</span>" in floor_fields
    assert "<span>Seats</span>" in floor_fields
    assert "<span>Store</span>" in floor_fields
    assert "Leftover table store ${row.code}" in floor_fields
    assert "rest-floor-actions" in tables_desk
    assert "Drag a table to place it on the floor." in tables_desk
    assert 'aria-label="Restaurant floor map"' in tables_desk
    assert "Place table ${row.code} on the floor" in tables_desk
    assert "Hold table ${row.code}" in tables_desk
    assert "Save table ${row.code}" in tables_desk
    assert "Retire table ${row.code}" in tables_desk
    assert "Edit table ${row.code} name" in tables_desk
    assert "Leftover table code ${row.code}" in tables_desk
    assert 'aria-label="Restaurant table store"' in tables_desk
    assert 'aria-label="Restaurant table room"' in tables_desk
    assert "No room." in tables_desk
    assert "store_id: tableForm.store_id.trim() || null" in restaurant
    # One Save covers code, name, seats, store and room; editing opens only for the chosen table.
    assert "saveWholeTable(row)" in tables_desk
    assert "Save leftover table store" not in tables_desk
    assert "editingTable === row.id" in tables_desk
    assert "code: edit.code.trim()" in restaurant
    assert "/restaurant/tables/${row.id}" in restaurant
    booking_desk = restaurant.split("tab === 'booking'", 1)[1].split("tab === 'orders'", 1)[0]
    assert "rest-order-form" in booking_desk
    assert "rest-order-list" in booking_desk
    assert "rest-order-line-fields" in booking_desk
    assert "rest-order-actions" in booking_desk
    assert "<span>Guest</span>" in booking_desk
    assert "<span>Phone</span>" in booking_desk
    assert "<span>When</span>" in booking_desk
    # Each booking is a card (time, guest, party, status); its edit form opens only on Edit.
    assert "rd-booking-card" in booking_desk
    assert "orderWord(row.status)" in booking_desk
    assert "editingBooking === row.id" in booking_desk
    assert "saveWholeBooking(row)" in booking_desk
    assert 'aria-label="Restaurant booking turn"' in booking_desk
    assert "No turn." in booking_desk
    assert "Leftover booking guest ${row.booking_number}" in booking_desk
    assert "Release table ${row.code}" in tables_desk
    assert "held: 'Held'" in restaurant
    assert "is-held" in (root / "frontend/app/globals.css").read_text(encoding="utf-8")
    assert "Choose a table first." in restaurant
    assert "15000" in restaurant
    assert "linesToSave" in restaurant
    assert "Add at least one menu item" in restaurant
    orders_desk = restaurant.split("tab === 'orders'", 1)[1].split("tab === 'kitchen'", 1)[0]
    assert "Add restaurant menu item" in orders_desk
    assert "Add leftover item to ${row.order_number}" in orders_desk
    assert "rest-order-form" in orders_desk
    assert "rest-order-line-fields" in orders_desk
    assert "rest-order-actions" in orders_desk
    assert "Leftover menu item ${row.order_number}" in orders_desk
    assert "Leftover new quantity ${row.order_number}" in orders_desk
    assert "Leftover new extra ${extra.name} on ${row.order_number}" in orders_desk
    assert "leftoverNewItems[row.id]" in orders_desk
    assert "Save leftover notes on ${row.order_number}" in orders_desk
    assert "Leftover customer name ${row.order_number}" in orders_desk
    assert "Leftover payment method ${row.order_number}" in orders_desk
    assert "Leftover service mode ${row.order_number}" in orders_desk
    assert "Save leftover service on ${row.order_number}" in orders_desk
    assert "Leftover service table ${row.order_number}" in orders_desk
    assert "Save leftover payment on ${row.order_number}" in orders_desk
    assert "Save leftover customer on ${row.order_number}" in orders_desk
    assert "Leftover delivery address ${row.order_number}" in orders_desk
    assert "Save leftover delivery address on ${row.order_number}" in orders_desk
    assert "(leftoverServiceModes[row.id] ?? row.service_mode) === 'delivery'" in orders_desk
    assert "customer_name: (leftoverCustomerNames[row.id] ?? row.customer_name ?? '').trim() || null" in restaurant
    assert "Remove leftover ${item.name} on ${row.order_number}" in orders_desk
    assert "Leftover quantity ${item.name} on ${row.order_number}" in orders_desk
    assert "Save leftover quantity ${item.name} on ${row.order_number}" in orders_desk
    assert "Leftover price ${item.name} on ${row.order_number}" in orders_desk
    assert "Save leftover price ${item.name} on ${row.order_number}" in orders_desk
    assert "Leftover station ${item.name} on ${row.order_number}" in orders_desk
    assert "Save leftover station ${item.name} on ${row.order_number}" in orders_desk
    assert "Leftover course ${item.name} on ${row.order_number}" in orders_desk
    assert "Save leftover course ${item.name} on ${row.order_number}" in orders_desk
    assert 'aria-label="Restaurant order course"' in orders_desk
    assert 'aria-label="Restaurant delivery zone"' in orders_desk
    assert 'aria-label="Add restaurant delivery zone"' in orders_desk
    assert "No delivery zones yet." in orders_desk
    assert 'aria-label="Restaurant online food orders"' in orders_desk
    assert 'aria-label="Open online food orders"' in orders_desk
    assert "Online food orders are closed." in orders_desk
    assert "Pay at the counter" in orders_desk
    assert 'aria-label="Restaurant sold out"' in orders_desk
    assert "Nothing is sold out." in orders_desk
    assert 'aria-label="Mark menu item sold out"' in orders_desk
    assert "This does not change stock." in orders_desk
    assert 'aria-label="Restaurant order covers"' in orders_desk
    assert "No covers." in orders_desk
    assert "Save leftover covers on ${row.order_number}" in orders_desk
    assert 'aria-label="Restaurant order allergy"' in orders_desk
    assert "No allergy." in orders_desk
    assert "Save leftover allergy on ${row.order_number}" in orders_desk
    assert 'aria-label="Restaurant order ready by"' in orders_desk
    assert "No ready time." in orders_desk
    assert "Save leftover ready by on ${row.order_number}" in orders_desk
    assert 'aria-label="Restaurant order rush"' in orders_desk
    assert "Not rushed." in orders_desk
    assert "Mark ${row.order_number} rush" in orders_desk
    assert "No server." in orders_desk
    assert "No opened time." in orders_desk
    assert 'aria-label="Restaurant order phone"' in orders_desk
    assert "No phone." in orders_desk
    assert "No item note." in orders_desk
    assert 'aria-label="Restaurant item hold"' in orders_desk
    assert "Not held." in orders_desk
    assert 'aria-label="Restaurant item seat"' in orders_desk
    assert "No seat." in orders_desk
    assert 'aria-label="Restaurant order pager"' in orders_desk
    assert "No pager." in orders_desk
    assert 'aria-label="Restaurant order cutlery"' in orders_desk
    assert "No cutlery." in orders_desk
    assert 'aria-label="Restaurant order email"' in orders_desk
    assert "No email." in orders_desk
    assert 'aria-label="Restaurant order occasion"' in orders_desk
    assert "No occasion." in orders_desk
    assert 'aria-label="Restaurant item spice"' in orders_desk
    assert "No spice." in orders_desk
    assert 'aria-label="Restaurant item doneness"' in orders_desk
    assert "No doneness." in orders_desk
    assert 'aria-label="Restaurant order fire at"' in orders_desk
    assert "No fire time." in orders_desk
    assert 'aria-label="Restaurant order packaging"' in orders_desk
    assert "No packaging." in orders_desk
    assert 'aria-label="Restaurant order high chair"' in orders_desk
    assert "No high chair." in orders_desk
    assert 'aria-label="Restaurant order diet"' in orders_desk
    assert "No diet." in orders_desk
    assert 'aria-label="Restaurant order allergen"' in orders_desk
    assert "No allergen." in orders_desk
    assert 'aria-label="Restaurant order source"' in orders_desk
    assert "No source." in orders_desk
    assert 'aria-label="Restaurant order vehicle"' in orders_desk
    assert "No vehicle." in orders_desk
    assert 'aria-label="Restaurant order bay"' in orders_desk
    assert "No bay." in orders_desk
    assert 'aria-label="Restaurant order handoff"' in orders_desk
    assert "No handoff." in orders_desk
    assert 'aria-label="Restaurant order bill"' in orders_desk
    assert "No bill asked." in orders_desk
    assert 'aria-label="Restaurant order arrived"' in orders_desk
    assert "Not arrived." in orders_desk
    assert 'aria-label="Restaurant order receipt"' in orders_desk
    assert "No receipt." in orders_desk
    assert 'aria-label="Restaurant order quoted wait"' in orders_desk
    assert "No quoted wait." in orders_desk
    assert 'aria-label="Restaurant service charge"' in orders_desk
    assert 'aria-label="Save restaurant service charge"' in orders_desk
    assert "No tax." in orders_desk
    assert "No service charge." in orders_desk
    assert "Completing a bill posts the ingredient cost to cost of goods and takes it off inventory." in orders_desk
    assert "A menu item with no recipe uses its own stock and cost." in orders_desk
    assert "A menu item with no recipe uses its own stock and cost." not in hotel
    assert "A restaurant bill cannot be put on credit." in orders_desk
    assert "A restaurant bill cannot be put on credit." not in hotel
    assert '<option value="credit">Credit</option>' not in orders_desk
    assert 'aria-label="Restaurant item note"' in orders_desk
    assert 'alt="Online food order code"' in orders_desk
    assert "line_courses" in restaurant
    assert "line_stations" in restaurant
    assert "line_prices" in restaurant
    assert "Leftover extra ${extra.name} on ${item.name} ${row.order_number}" in orders_desk
    assert "Save leftover extras ${item.name} on ${row.order_number}" in orders_desk
    assert "line_modifiers" in restaurant
    assert 'aria-label="Restaurant order store"' in orders_desk
    assert "store_id: orderForm.store_id.trim() || null" in restaurant
    assert "Leftover order store ${row.order_number}" in orders_desk
    assert "Save leftover store on ${row.order_number}" in orders_desk
    assert "line_quantities" in restaurant
    assert "remove_line_ids" in restaurant
    assert "{menuItems.map((row) => (" in orders_desk
    assert 'aria-label="Restaurant kitchen notes"' in orders_desk
    assert "notes: orderForm.notes.trim() || null" in restaurant
    assert 'aria-label="Restaurant delivery address"' in orders_desk
    assert "Enter a delivery address" in restaurant
    assert "delivery_address" in restaurant
    assert 'aria-label="Restaurant extra name"' in orders_desk
    assert "Save restaurant extra" in orders_desk
    assert "Retire extra ${row.name}" in orders_desk
    assert "Save leftover extra ${row.name}" in orders_desk
    assert "Leftover extra name ${row.name}" in orders_desk
    assert "Leftover extra price ${row.name}" in orders_desk
    assert "Leftover extra group name ${group.name}" in orders_desk
    assert "Save leftover extra group ${group.name}" in orders_desk
    assert "Retire leftover extra group ${group.name}" in orders_desk
    assert "/restaurant/modifier-groups/${group.id}" in orders_desk
    assert "name: leftoverExtraNames[row.id] ?? row.name" in orders_desk
    assert "/restaurant/modifiers/${row.id}" in orders_desk
    assert "/restaurant/modifiers/${row.id}/retire" in orders_desk
    assert "No extras yet." in orders_desk
    assert "modifier_ids" in restaurant
    assert "item.prep_status" in orders_desk
    assert "Void order ${row.order_number}" in orders_desk
    assert "Refund order ${row.order_number}" in orders_desk
    assert "No orders yet." in orders_desk
    assert "['Service', orderWord(row.service_mode)]" in orders_desk
    assert "<span>Tender</span>" in orders_desk
    assert "<span>Menu item</span>" in orders_desk
    assert "row.customer_name" in orders_desk
    assert "tenderLabel(row)" in orders_desk
    assert "orderWord(row.payment_method)" in restaurant
    kitchen_desk = restaurant.split("tab === 'kitchen'", 1)[1].split("tab === 'recipes'", 1)[0]
    assert "No tickets in the kitchen." in kitchen_desk
    assert "No tickets at the bar." in kitchen_desk
    assert "Kitchen sound is off." in kitchen_desk
    assert 'aria-label="Turn on kitchen sound"' in kitchen_desk
    assert "A new ticket plays a short chime when the kitchen refreshes." in kitchen_desk
    assert 'aria-label="Restaurant clock"' in kitchen_desk
    assert "Not clocked in." in kitchen_desk
    assert 'aria-label="Clock in"' in kitchen_desk
    assert "No one is clocked in." in kitchen_desk
    assert "This does not open the till." in kitchen_desk
    assert "playKitchenChime" in restaurant
    assert "stationQueue('bar'" in kitchen_desk
    assert "'Bar queue'" in kitchen_desk
    assert "row.customer_name" in restaurant
    assert "['Guest', row.customer_name]" in restaurant
    assert 'className="rd-mini" aria-label="Restaurant open orders"' in restaurant
    # Kitchen display: one big Start / Ready per dish, allergies flagged on the ticket.
    assert "rd-kds-list" in restaurant and "rd-ticket-alert" in restaurant
    assert "orderWord(row.service_mode)" in restaurant
    recipes_desk = restaurant.split("tab === 'recipes'", 1)[1].split("tab === 'dashboard'", 1)[0]
    assert 'aria-label="Restaurant menu station"' in recipes_desk
    assert "Save restaurant menu station" in recipes_desk
    assert "Add restaurant ingredient" in recipes_desk
    assert "{ingredientItems.map((row) => (" in recipes_desk
    assert "!recipeIngredientIds.has(row.id) || recipeMenuIds.has(row.id)" in recipes_desk
    assert "<span>Menu item</span>" in recipes_desk
    assert "<span>Ingredient</span>" in recipes_desk
    assert "<span>Warehouse</span>" in recipes_desk
    assert "['Station', orderWord(row.station)]" in recipes_desk
    assert 'aria-label="Restaurant recipe cook time"' in recipes_desk
    assert "No cook time." in recipes_desk
    assert 'aria-label="Restaurant recipe servings"' in recipes_desk
    assert "No servings." in recipes_desk
    assert "No recipes yet." in recipes_desk
    assert "Restaurant recipes" in recipes_desk
    assert 'onSubmit={saveStation}' in recipes_desk
    assert "await createRecipe(event);" in recipes_desk
    assert 'className="rest-order-list" aria-label="Restaurant recipes"' in recipes_desk
    assert 'onSubmit={saveWaste}' in restaurant
    # Recipes and waste: one Save per recipe; edit opens only for the chosen recipe.
    assert "editingRecipe === row.id" in recipes_desk and "Save leftover cook time" not in recipes_desk
    assert "Leftover recipe name ${row.name}" in recipes_desk
    assert "Leftover recipe line quantity ${line.name} on ${row.name}" in recipes_desk
    assert "Remove leftover recipe line ${line.name} on ${row.name}" in recipes_desk
    assert "Leftover recipe ingredient ${row.name}" in recipes_desk
    assert "Add leftover recipe ingredient ${row.name}" in recipes_desk
    assert "Save leftover recipe ${row.name}" in recipes_desk
    assert "Retire leftover recipe ${row.name}" in recipes_desk
    assert "/restaurant/recipes/${row.id}/retire" in recipes_desk
    assert "/restaurant/recipes/${row.id}" in restaurant
    assert "Waste takes an ingredient off hand." in restaurant
    assert "The cost is posted to operating expenses and taken off inventory." in restaurant
    assert "The cost is posted to operating expenses and taken off inventory." not in hotel
    assert "row.journal_entry_id ? ' · On the books' : ''" in restaurant
    assert "Record restaurant waste" in restaurant
    assert "No waste recorded yet." in restaurant
    assert 'aria-label="Restaurant waste history"' in restaurant
    assert 'aria-label="Restaurant waste warehouse"' in restaurant
    assert "warehouse_id: wasteForm.warehouse_id.trim() || null" in restaurant
    assert "Choose an ingredient first." in restaurant
    assert "['Reports', '/restaurant/reports', 'reports']" in (root / "frontend/lib/tenantNav.ts").read_text(encoding="utf-8")
    assert "['Waste', '/restaurant?tab=waste', 'restaurant']" in (root / "frontend/lib/tenantNav.ts").read_text(encoding="utf-8")
    restaurant_finance = nav.split("id: 'restaurant-finance'", 1)[1].split("id: 'restaurant-people'", 1)[0]
    assert "['Pay suppliers', '/restaurant/payables', 'credit']" in restaurant_finance
    assert "/credit?kind=receivable" not in restaurant_finance
    assert "Add at least one ingredient" in restaurant
    assert "Choose an ingredient first" in restaurant
    assert "item.modifiers" in restaurant
    assert "Mark ${item.name} ready on ${row.order_number}" in restaurant
    assert "<span>Tables</span>" in restaurant
    assert "function tableFloor" in restaurant
    kitchen_kpi = restaurant.split("<span>Kitchen and bar</span>", 1)[1].split("<span>Tables</span>", 1)[0]
    assert "summary.tables" not in kitchen_kpi
    tables_kpi = restaurant.split("<span>Tables</span>", 1)[1].split("rd-alerts", 1)[0]
    assert "summary.tables" in tables_kpi
    assert "Restaurant is not available for this company." in restaurant
    assert "Open front-desk float" in hotel
    assert "not the shop till and not a card charge" in hotel
    assert "Open shift" not in hotel
    reports = (root / "frontend/app/(dashboard)/reports/page.tsx").read_text(encoding="utf-8")
    tax_page = (root / "frontend/app/(dashboard)/tax/page.tsx").read_text(encoding="utf-8")
    dash = (root / "frontend/app/(dashboard)/dashboard/page.tsx").read_text(encoding="utf-8")
    assert "Checkout invoice / shop till" in reports
    assert "Invoice / POS" in reports
    assert "No menu items sold in this period" in reports
    assert "No items sold in this period" in reports
    assert "No products sold in this period" in reports
    assert "Low-ingredient suggestions" in reports
    assert "Low-supply suggestions" in reports
    assert "Low-stock suggestions" in reports
    assert "No ingredient movements for these dates" in reports
    assert "No supply movements for these dates" in reports
    assert "No stock movements for these dates" in reports
    assert "Ingredient valuation (standard cost)" in reports
    assert "Supply valuation (standard cost)" in reports
    assert "Stock valuation (standard cost)" in reports
    assert "Ingredient count variances" in reports
    assert "Supply count variances" in reports
    assert "Stock count variances" in reports
    assert "No ingredient count variances for this filter" in reports
    assert "No supply count variances for this filter" in reports
    assert "No stock count variances for this filter" in reports
    assert "rest-report-sched" in reports
    assert "restaurantReports ? 4 : 6" in reports
    assert "<th>Schedule</th>" in reports
    assert "<th>Name</th>" in reports
    assert "<th>Report</th>" in reports
    assert "<th>Recipients</th>" in reports
    assert "<th>Last run</th>" in reports
    assert "No recipients" in reports
    assert "Not run yet" in reports
    assert "No email reports yet. Create a schedule when you want a report sent on its own." in reports
    assert "No schedules for this filter" in reports
    assert "No schedules yet." in reports
    assert "rest-sold-table" in reports
    assert "Menu item cost uses the ingredient cost." in reports
    assert "A restaurant till return comes off menu items sold." in reports
    assert "A restaurant till tax stays off this menu amount. The till receipt keeps the tax." in reports
    assert "A restaurant till return comes off today sales." in reports
    assert "A restaurant till return comes off this customer. The original receipt stays on the till report." in reports
    assert "A completed restaurant bill is included for this customer." in reports
    assert "A restaurant till return comes off this staff member. The original receipt stays on the till report." in reports
    assert "A completed restaurant bill is included for the staff member who rang it." in reports
    assert "A restaurant till return comes off this department. The original receipt stays on the till report." in reports
    assert "A completed restaurant bill is included for the department of the staff member who rang it." in reports
    assert "A restaurant till return comes off this store. The original receipt stays on the till report." in reports
    assert "A completed restaurant bill is included for the store on the bill." in reports
    assert "A completed restaurant bill is included in profit and loss for the store on the bill." in reports
    assert "Restaurant waste at this store is included in these operating expenses." in reports
    assert "A restaurant till return follows the store on the original receipt." in reports
    assert "A completed restaurant bill takes this store value down when the stock sits in that store's warehouse." in reports
    assert "A restaurant till return puts the stock back in the store on the original receipt." in reports
    assert "A restaurant till return comes off this till tax. The original receipt stays on the till report." in tax_page
    assert "A completed restaurant bill is included in this bill tax." in tax_page
    assert "A restaurant till return comes off this list. The original receipt stays on the till report." in dash
    assert "A restaurant till return comes off today sales." not in hotel
    assert "A restaurant till return comes off this customer. The original receipt stays on the till report." not in hotel
    assert "A completed restaurant bill is included for this customer." not in hotel
    assert "A restaurant till return comes off this staff member. The original receipt stays on the till report." not in hotel
    assert "A completed restaurant bill is included for the staff member who rang it." not in hotel
    assert "A restaurant till return comes off this department. The original receipt stays on the till report." not in hotel
    assert "A completed restaurant bill is included for the department of the staff member who rang it." not in hotel
    assert "A restaurant till return comes off this store. The original receipt stays on the till report." not in hotel
    assert "A completed restaurant bill is included for the store on the bill." not in hotel
    assert "A completed restaurant bill is included in profit and loss for the store on the bill." not in hotel
    assert "Restaurant waste at this store is included in these operating expenses." not in hotel
    assert "A restaurant till return follows the store on the original receipt." not in hotel
    assert "A completed restaurant bill takes this store value down when the stock sits in that store's warehouse." not in hotel
    assert "A restaurant till return puts the stock back in the store on the original receipt." not in hotel
    assert "A restaurant till return comes off this till tax. The original receipt stays on the till report." not in hotel
    assert "A completed restaurant bill is included in this bill tax." not in hotel
    assert "A restaurant till return comes off this list. The original receipt stays on the till report." not in hotel
    assert "A restaurant till return comes off this discount. The original receipt stays on the till report." not in hotel
    assert "A restaurant till return follows the store on the original receipt." not in hotel
    assert "A completed restaurant bill is included in this tax." not in hotel
    assert "A restaurant till return comes off this tax. The original receipt stays on the till report." not in hotel
    assert "A restaurant till return comes off menu items sold." not in hotel
    assert "A restaurant till tax stays off this menu amount. The till receipt keeps the tax." not in hotel
    assert "A restaurant till tax stays off this sales amount. The till receipt keeps the tax." not in hotel
    assert "A restaurant till discount comes off this sales amount. The menu amount stays." not in hotel
    assert "A restaurant till discount is included in this discount. The menu amount stays." not in hotel
    assert "A restaurant bill with no store stays off a store filter." not in hotel
    assert "A restaurant till return with no store stays off a store filter." not in hotel
    assert "Menu item cost uses the ingredient cost." not in hotel
    assert "restaurantReports ? 3 : 4" in reports
    assert "<th>Menu item</th>" in reports
    assert "<th>Sold</th>" in reports
    assert "<th>SKU</th>" in reports
    assert "<th>Qty</th>" in reports
    assert "No code" in reports
    assert "No menu items sold in this period" in reports
    assert "rest-staff-sales" in reports
    assert "restaurantReports ? 4 : 8" in reports
    assert "<th>Staff</th>" in reports
    assert "<th>Bills</th>" in reports
    assert "<th>Restaurant till</th>" in reports
    assert "<th>Name</th>" in reports
    assert "<th>Department</th>" in reports
    assert "<th>Role</th>" in reports
    assert "<th>Invoices</th>" in reports
    assert "<th>Avg ticket</th>" in reports
    assert "No department" in reports
    assert "No role" in reports
    assert "Average bill" in reports
    assert "No staff sales for these dates. Widen the dates, then choose Generate." in reports
    assert "No staff sales for these dates; widen the dates, then choose Generate." in reports
    assert "rest-cust-sales" in reports
    assert "restaurantReports ? 4 : 6" in reports
    assert "<th>Customer</th>" in reports
    assert "<th>Frequency</th>" in reports
    assert "No email" in reports
    assert "Visits " in reports
    assert "No customer sales for these dates. Widen the dates, then choose Generate." in reports
    assert "No customer sales for these dates; widen the dates, then choose Generate." in reports
    assert "rest-dept-sales" in reports
    assert "restaurantReports ? 4 : 7" in reports
    assert "<th>Department</th>" in reports
    assert "<th>Code</th>" in reports
    assert "Sales " in reports
    assert "No department sales for these dates. Widen the dates, then choose Generate." in reports
    assert "No department sales for these dates; widen the dates, then choose Generate." in reports
    assert "rest-ing-value" in reports
    assert "<th>On hand</th>" in reports
    assert "<th>SKU</th>" in reports
    assert "<th>Qty</th>" in reports
    assert "<th>Unit cost</th>" in reports
    assert "No cost" in reports
    assert "No ingredients to value yet." in reports
    assert "rest-ing-move" in reports
    assert "restaurantReports ? 4 : 9" in reports
    assert "<th>Change</th>" in reports
    assert "<th>Record</th>" in reports
    assert "<th>Before → after</th>" in reports
    assert "<th>Ref</th>" in reports
    assert "No person" in reports
    assert "No reason" in reports
    assert "No record" in reports
    assert "Was " in reports
    assert "No ingredient movements for these dates. Widen the dates, then choose Generate." in reports
    assert "rest-expiry" in reports
    assert "restaurantReports ? 4 : 6" in reports
    assert "Lots nearing expiry" in reports
    assert "<th>Days</th>" in reports
    assert "restaurantReports ? 'Lot' : 'Batch'" in reports
    assert "No lot" in reports
    assert "Days left " in reports
    assert "No lots nearing expiry for this filter." in reports
    assert "No batches nearing expiry for this filter." in reports
    assert "rest-count-var" in reports
    assert "restaurantReports ? 4 : 7" in reports
    assert "<th>Expected</th>" in reports
    assert "No warehouse" in reports
    assert "No count" in reports
    assert "No ingredient count variances for this filter." in reports
    assert "rest-po-pending" in reports
    assert "Orders still to receive" in reports
    assert "<th>Order</th>" in reports
    assert "<th>Still open</th>" in reports
    assert "<th>PO</th>" in reports
    assert "<th>Outstanding qty</th>" in reports
    assert "No supplier" in reports
    assert "Received " in reports
    assert "No orders are still waiting to be received." in reports
    assert "No pending purchase orders for these filters; change the dates or status, then choose Generate." in reports
    assert "rest-exp-budget" in reports
    assert "Costs against the budget" in reports
    assert "<th>Cost group</th>" in reports
    assert "<th>Spent</th>" in reports
    assert "<th>Budget (scaled)</th>" in reports
    assert "<th>Actual</th>" in reports
    assert "<th>Variance</th>" in reports
    assert "Difference " in reports
    assert "No cost groups to compare yet." in reports
    assert "No spend yet" in reports
    assert "rest-cash-flow" in reports
    assert "<th>Movement</th>" in reports
    assert "<th>Date</th>" in reports
    assert "<th>Entry</th>" in reports
    assert "<th>Activity</th>" in reports
    assert "No activity" in reports
    assert "No cash movements in this period." in reports
    assert "Money in and out of cash and the bank" in reports
    assert "Cash and bank movements" in reports
    assert "rest-pnl" in reports
    assert "restaurantReports ? 2 : 4" in reports
    assert "<th>Account</th>" in reports
    assert "<th>Code</th>" in reports
    assert "<th>Name</th>" in reports
    assert "Ingredient cost" in reports
    assert "Running costs" in reports
    assert "'COGS'" in reports
    assert "Operating expenses" in reports
    assert "No income or costs for this period." in reports
    assert "No income/expense activity for this filter" in reports
    assert "rest-trial" in reports
    assert "restaurantReports ? 3 : 5" in reports
    assert "<th>Debit</th>" in reports
    assert "<th>Credit</th>" in reports
    assert "In balance" in reports
    assert "Out of balance" in reports
    assert "'Balanced'" in reports
    assert "'Not balanced'" in reports
    assert "No balances for this date. Change the date, then choose Generate." in reports
    assert "No balances for this as-of date; change the date, then choose Generate." in reports
    assert "this location only (bills, restaurant till, costs, returns)" in reports
    assert "this location only (checkout invoices, shop till, expenses, returns)" in reports
    assert "this location only (sales, till, expenses, returns)" in reports
    assert "rest-bs" in reports
    assert "No assets yet." in reports
    assert "Nothing owed yet." in reports
    assert "No equity yet." in reports
    assert "Owed and owner stake" in reports
    assert "Liabilities + equity" in reports
    assert "<th>Δ</th>" in reports
    assert "<th>Change</th>" in reports
    assert "String(data.balanced)" in reports
    assert "rest-acct-lines" in reports
    assert "restaurantReports ? 4 : 6" in reports
    assert "<th>When</th>" in reports
    assert "<th>Memo</th>" in reports
    assert "No memo" in reports
    assert "No movements for this account in these dates." in reports
    assert "No posted lines for this account in the date range" in reports
    assert "Choose an account, then choose Generate." in reports
    assert "Select an account for the statement" in reports
    assert "rest-po-return" in reports
    assert "<th>Supplier</th>" in reports
    assert "<th>Status</th>" in reports
    assert "No supplier" in reports
    assert "No reason" in reports
    assert "No returns to suppliers for these dates. Change the dates or status, then choose Generate." in reports
    assert "No purchase returns for these filters; change the dates or status, then choose Generate." in reports
    assert "restaurant={restaurantReports}" in reports
    sheets = (root / "frontend/components/SalesReportSheets.tsx").read_text(encoding="utf-8")
    assert "rest-bill-return" in sheets
    assert "No bill returns for these dates." in sheets
    assert "rest-detailed-sales" in sheets
    assert "No bills in this period." in sheets
    assert "<th>Bill</th>" in sheets
    assert "No source" in sheets
    assert "rest-till-sales" in sheets
    assert "No restaurant till receipts in this period." in sheets
    assert "<th>Receipt</th>" in sheets
    assert "No cashier" in sheets
    assert "No tender" in sheets
    assert "rest-quotations" in sheets
    assert "No quotations for these dates." in sheets
    assert "No quotations in this period." in sheets
    assert "<th>Quotation</th>" in sheets
    assert "No status" in sheets
    assert "rest-menu-sales" in sheets
    assert "No menu item sales for this period." in sheets
    assert "No category sales for this period." in sheets
    assert "No brand sales for this period." in sheets
    assert "No product sales for this period." in sheets
    assert "<th>Menu item</th>" in sheets
    assert "rest-discounts" in sheets
    assert "No bill discounts in this period." in sheets
    assert "No discounts in this period." in sheets
    assert "<th>Discount</th>" in sheets
    assert "rest-tenders" in sheets
    assert "No tenders in this period." in sheets
    assert "No payments in this period." in sheets
    assert "<th>Tender</th>" in sheets
    assert "<th>Payment method</th>" in sheets
    assert "This list does not charge a card." in sheets
    assert "Gift cards and loyalty stay on retail sales." in sheets
    assert "rest-credit" in sheets
    assert "No open bills on account." in sheets
    assert "No outstanding customer balances." in sheets
    assert "<th>Guest</th>" in sheets
    assert "No sales returns for this period." in sheets
    assert "No customer" in sheets
    assert "<th>Customer</th>" in sheets
    assert "A refunded table bill is taken out of completed sales and listed here." in sheets
    assert "A posted return is not taken out of the other sales reports." not in sheets
    assert "Posted returns are not subtracted from the other sales reports." in sheets
    assert "rest-sold-lines" in sheets
    assert "<th>Menu item</th>" in sheets
    assert "<th>SKU</th>" in sheets
    assert "<th>Sales total</th>" in sheets
    assert "No menu items sold in this period." in sheets
    assert "No products sold in this period." in sheets
    assert "No items sold in this period." in sheets
    assert "A refunded table bill is taken out of this list and listed on Bill returns." in sheets
    assert "A restaurant till return comes off this list and is listed on Bill returns." in sheets
    assert "A completed restaurant bill is included in this tax." in sheets
    assert "A restaurant till return comes off this tax. The original receipt stays on the till report." in sheets
    assert "A restaurant till tax stays off this sales amount. The till receipt keeps the tax." in sheets
    assert "A restaurant till discount comes off this sales amount. The menu amount stays." in sheets
    assert "A restaurant till discount is included in this discount. The menu amount stays." in sheets
    assert "A restaurant bill with no store stays off a store filter." in sheets
    assert "A restaurant till return with no store stays off a store filter." in sheets
    assert "A restaurant till tax stays off this menu amount. The till receipt keeps the tax." in sheets
    assert "A restaurant till return comes off menu items sold. The original receipt stays on the till report." in sheets
    assert "A restaurant till return follows the store on the original receipt." in sheets
    assert "A restaurant till return comes off this list. The original receipt stays on the till report." in sheets
    assert "A restaurant till return comes off this tender. The original receipt stays on the till report." in sheets
    assert "A restaurant till return comes off this discount. The original receipt stays on the till report." in sheets
    assert "A restaurant till return stays on the receipt and is listed on Bill returns." not in sheets
    assert "No code" in sheets
    groups = (root / "frontend/lib/reportGroups.ts").read_text(encoding="utf-8")
    assert "Shop till sales" in groups
    assert "name: 'POS sales'" in groups
    assert "name: 'Shop till sales'" in groups
    assert "name: 'Restaurant till sales'" in groups
    assert "name: 'Ingredient count variances'" in groups
    assert "name: 'Returns to suppliers'" in groups
    assert "name: 'Purchase returns'" in groups
    assert "name: 'Bill returns'" in groups
    assert "name: 'Sales returns'" in groups
    assert "name: 'Stock count variances'" in groups
    assert "offline_complete_claimed" not in sales

