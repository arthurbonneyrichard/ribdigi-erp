"""Restaurant till is its own screen: restaurant companies never use the retail POS."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TILL = ROOT / "frontend/app/(dashboard)/restaurant/till/page.tsx"
TILL_CSS = ROOT / "frontend/app/(dashboard)/restaurant/till/restaurant-till.css"
NAV = ROOT / "frontend/lib/tenantNav.ts"


def test_restaurant_sidebar_links_its_own_till():
    nav = NAV.read_text(encoding="utf-8")
    assert "['Restaurant till', '/restaurant/till', 'restaurant']" in nav
    assert "['Restaurant till', '/pos'" not in nav


def test_retail_pos_is_off_restaurant_menus():
    nav = NAV.read_text(encoding="utf-8")
    start = nav.index("if (path === '/pos') {")
    rule = nav[start : nav.index("}", start)]
    assert "'restaurant'" not in rule
    assert "'retail'" in rule


def test_restaurant_till_only_calls_restaurant_order_apis():
    page = TILL.read_text(encoding="utf-8")
    assert "'/restaurant/orders'" in page
    assert "/complete`" in page and "/send`" in page
    # No retail till endpoints or retail till styles.
    assert "/pos/" not in page
    assert "tpos" not in page
    assert "pos-modern.css" not in page


def test_restaurant_till_has_its_own_look():
    css = TILL_CSS.read_text(encoding="utf-8")
    assert "--rt-accent" in css
    assert ".tpos" not in css


FRONT = ROOT / "frontend/app/(dashboard)/restaurant"


def test_restaurant_sidebar_uses_its_own_orders_bills_and_guests():
    nav = NAV.read_text(encoding="utf-8")
    assert "['Orders', '/restaurant/orders', 'restaurant']" in nav
    assert "['Bills', '/restaurant/bills', 'restaurant']" in nav
    assert "['Guests', '/restaurant/guests', 'restaurant']" in nav
    start = nav.index("export const RESTAURANT_NAV_GROUPS")
    groups = nav[start : nav.index("export const FMCG_NAV_ITEMS")]
    assert "'/sales'" not in groups and "'/customers'" not in groups and "'/pos'" not in groups
    rule = nav[nav.index("if (path === '/sales' || path === '/customers') {") :]
    rule = rule[: rule.index("}")]
    assert "'restaurant'" not in rule


def test_restaurant_desk_screens_only_call_restaurant_apis():
    for name in ("orders", "bills", "guests"):
        page = (FRONT / name / "page.tsx").read_text(encoding="utf-8")
        assert "restaurant-desk.css" in page
        assert "/pos/" not in page and "'/sales" not in page and "'/customers" not in page
    assert "'/restaurant/guests'" in (FRONT / "guests/page.tsx").read_text(encoding="utf-8")
    assert "'/restaurant/till/shifts'" in (FRONT / "bills/page.tsx").read_text(encoding="utf-8")
    css = (FRONT / "restaurant-desk.css").read_text(encoding="utf-8")
    assert "--rd-brand:#4AB012" in css and ".tpos" not in css


def test_restaurant_till_counts_its_own_drawer():
    page = TILL.read_text(encoding="utf-8")
    assert "'/restaurant/till/shift/open'" in page
    assert "/close`" in page and "/cash`" in page
    # Extras are charged once per line, like the bill.
    assert "return line.quantity * line.price + line.modifier_total;" in page
    assert "item.line_total" in page


def test_public_website_orders_and_books_on_one_page():
    site = (ROOT / "frontend/components/restaurant-site/RestaurantSite.tsx").read_text(encoding="utf-8")
    assert "/public/restaurant-site/" in site
    assert "/order`" in site and "/book`" in site
    assert "pre_order" in site and "Follow your order" in site
    for route in ("book", "order"):
        page = (ROOT / f"frontend/app/{route}/[slug]/page.tsx").read_text(encoding="utf-8")
        assert "RestaurantSite" in page
    nav = NAV.read_text(encoding="utf-8")
    assert "['Website and booking', '/restaurant?tab=booking', 'restaurant']" in nav
