"""Phone layout: desks stay inside the screen and keep the side-nav gutter."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CSS = ROOT / "frontend/app/globals.css"
SF = ROOT / "frontend/app/storefront/storefront.css"
POS = ROOT / "frontend/app/(dashboard)/pos/pos-modern.css"
LAYOUT = ROOT / "frontend/app/layout.tsx"


def test_phone_layout_uses_full_width_and_stacks_desk_chrome():
    css = CSS.read_text(encoding="utf-8")
    layout = LAYOUT.read_text(encoding="utf-8")
    assert "max-width:100vw" not in css
    assert ".main{padding:10px 8px 20px}" not in css
    # Tablet drawer still clears the edge tab; phones hide that tab.
    assert (
        ".shell:not(.is-pos) > .main{padding-left:calc(52px + env(safe-area-inset-left, 0px))}"
        in css
    )
    phone = css.split("@media (max-width:720px){")[-1]
    assert ".mobile-side-nav{display:none !important}" in phone
    assert "padding-left:max(14px,env(safe-area-inset-left,0px))" in phone
    assert "padding-right:max(14px,env(safe-area-inset-right,0px))" in phone
    assert "width:100%;max-width:100%" in phone
    assert "width:max-content;min-width:100%;max-width:none;table-layout:auto;white-space:nowrap" in phone
    assert (
        "display:table;table-layout:auto;width:max-content;min-width:100%;max-width:none;margin:0"
        in css
    )
    tablet = css.split("@media(min-width:721px){")[-1]
    assert "table-layout:auto;white-space:nowrap" in tablet
    assert ".purchase-ui-page .cat-table-wrap .table" in tablet
    assert ".sale-form-pair{" in phone
    assert ".sales-ui-page .list-table-wrap .table" in phone
    assert ".page-head,.list-page-head,.sales-desk-head,.cat-head,.users-page-head,.plat-hero{" in css
    assert "flex-direction:column;align-items:stretch" in css
    assert "viewportFit: 'cover'" in layout
    assert "width:100%;max-width:100%;margin:auto 0" in css
    assert ".login-split{" in css
    assert ".login-heading{" in css
    assert ".login-tagline{display:none}" in css
    assert ".login-forgot a,.login-legal a,.login-ghost{" in css
    assert "overflow-y:auto;-webkit-overflow-scrolling:touch" in css
    assert "max-height:100vh;max-height:100dvh" in css
    assert "@media(min-width:721px) and (max-width:899px){" in css
    assert "@media(min-width:900px){" in css
    assert "@media(max-width:720px) and (orientation:landscape)" in css

    sales = (ROOT / "frontend/app/(dashboard)/sales/sales-ui.css").read_text(encoding="utf-8")
    inv = (ROOT / "frontend/app/(dashboard)/inventory/inv-ui.css").read_text(encoding="utf-8")
    purch = (ROOT / "frontend/app/(dashboard)/purchasing/purchase-ui.css").read_text(encoding="utf-8")
    for desk in (sales, inv, purch):
        assert "@media (max-width: 720px)" in desk
        assert "width: max-content;" in desk
        assert "table-layout: auto;" in desk
    assert "width: max-content;" in sales.split("@media (max-width: 760px)")[-1]
    assert "white-space: nowrap;" in sales.split("@media (max-width: 760px)")[-1]


def test_storefront_and_pos_stack_on_phone():
    sf = SF.read_text(encoding="utf-8")
    pos = POS.read_text(encoding="utf-8")
    assert ".sf-bar{" in sf
    assert "align-items:stretch" in sf
    assert "grid-template-columns: minmax(0, 1fr)" in pos
    assert "repeat(2, minmax(0, 1fr))" in pos
