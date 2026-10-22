"""POS split workspace: cart left, catalog right, categories, keypad, receipt preview."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _css() -> str:
    return (ROOT / "frontend/app/globals.css").read_text(encoding="utf-8")


def _pos() -> str:
    return (ROOT / "frontend/app/(dashboard)/pos/page.tsx").read_text(encoding="utf-8")


def test_pos_split_layout_cart_left_catalog_right():
    css = _css()
    pos = _pos()
    compact = css.replace(" ", "").replace("\n", "")
    assert 'grid-template-areas:"cartcatalog"' in compact
    assert "grid-area:cart" in compact
    assert "grid-area:catalog" in compact
    assert 'aria-label="POS product categories"' in pos
    assert "tpos-cats" in pos
    assert "visibleRows.map" in pos
    assert "in-cart" in pos
    assert 'aria-label="POS keypad"' in pos
    assert "applyKeypad" in pos
    assert 'aria-label="Last receipt preview"' in pos
    assert "receiptPreviewFromCart" in pos
    assert "Add a product before charging" in pos
    assert 'aria-label="POS receipt paper"' in pos
    assert "payAsReprint ? 'Print' : 'Charge'" in pos
    assert "addToCart(r)" in pos
    assert "{r.sku}" in pos
    assert "client_request_id" in pos
    assert "enqueueOfflineSale" in pos
    assert "offline_complete_claimed" not in pos


def test_pos_cart_line_name_and_qty_compact():
    css = _css()
    pos = _pos()
    compact = css.replace(" ", "").replace("\n", "")
    assert "tpos-cart-name-text" in pos
    assert "tpos-cart-line-sub" in pos
    assert "tpos-qty pos-ui-qty" in pos
    assert 'className="tpos-line"' in pos
    assert "-webkit-line-clamp:2" in css
    assert "overflow-wrap:anywhere" in css
    assert 'grid-template-columns:minmax(0,1fr)4.35rem4.5rem22px' in compact
    assert "minmax(0,1fr) 10.5rem" not in css
    assert "width:2.6rem;min-width:2.6rem;height:44px" not in compact
    assert ".main.pos-ui-cart.pos-ui-qtybutton{width:20px;height:20px" in compact
    assert 'grid-template-areas:"cartcatalog"' in compact
    assert "offline_complete_claimed" not in pos
