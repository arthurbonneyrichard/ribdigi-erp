"""Restaurant stock and purchasing: the restaurant's own screens over the shared stock engine."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "frontend"
STOCK = (ROOT / "app/(dashboard)/restaurant/ingredients/page.tsx").read_text(encoding="utf-8")
BUY = (ROOT / "app/(dashboard)/restaurant/purchasing/page.tsx").read_text(encoding="utf-8")
NAV = (ROOT / "lib/tenantNav.ts").read_text(encoding="utf-8")
CSS = (ROOT / "app/(dashboard)/restaurant/restaurant-desk.css").read_text(encoding="utf-8")


def test_stock_screen_splits_ingredients_from_menu_items():
    assert "Ingredients <small>" in STOCK and "Menu items <small>" in STOCK
    # Menu = has a recipe or a kitchen/bar station; the rest are ingredients.
    assert "recipeMenu.has(p.id) || p.prep_station === 'kitchen' || p.prep_station === 'bar'" in STOCK
    assert "Running low" in STOCK and "Out of stock" in STOCK
    assert "Stock value (at cost)" in STOCK


def test_stock_actions_use_shared_engine():
    assert "'/inventory/stock-in'" in STOCK
    assert "`/inventory/adjust/${row!.id}`" in STOCK
    assert "reason: delta > 0 ? 'found' : 'lost'" in STOCK
    assert "category: 'Ingredients'" in STOCK
    assert "'/restaurant/sold-out'" in STOCK
    # No retail jargon on the restaurant stock screen.
    for word in ("SKU", "Brand", "Variant", "Barcode"):
        assert word not in STOCK


def test_purchasing_order_send_receive_flow():
    assert "'/purchasing/orders'" in BUY
    assert "`/purchasing/orders/${po.id}/issue`" in BUY
    assert "'/purchasing/grn'" in BUY
    assert "po_item_id: i.id, received_qty: n, accepted_qty: n" in BUY
    assert "/purchasing/suggestions/low-stock?include_open=true" in BUY
    assert "Receive delivery into stock" in BUY
    assert "`/purchasing/orders/${po.id}/cancel`" in BUY
    assert "Owed to suppliers" in BUY


def test_restaurant_nav_uses_own_stock_screens():
    start = NAV.index("export const RESTAURANT_NAV_GROUPS")
    block = NAV[start : NAV.index("];", start)]
    assert "['Ingredients', '/restaurant/ingredients', 'inventory']" in block
    assert "['Menu items', '/restaurant/ingredients?tab=menu', 'inventory']" in block
    assert "['Purchasing', '/restaurant/purchasing', 'purchasing']" in block
    assert "['Suppliers', '/restaurant/purchasing?tab=suppliers', 'purchasing']" in block
    assert "/inventory?tab=products" not in block
    assert "/purchasing?tab=grn" not in block


def test_stock_rows_styled_inside_desk_scope():
    assert ".main .rdesk .rd-stock-row{" in CSS
    assert ".main .rdesk .rd-po-line{" in CSS
