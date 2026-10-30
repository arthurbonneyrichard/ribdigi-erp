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
