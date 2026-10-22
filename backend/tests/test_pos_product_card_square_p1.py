"""POS product tiles stay compact 1:1 squares with name/SKU/price/stock."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_pos_product_cards_are_compact_squares():
    css = (ROOT / "frontend/app/globals.css").read_text(encoding="utf-8")
    pos = (ROOT / "frontend/app/(dashboard)/pos/page.tsx").read_text(encoding="utf-8")
    assert "aspect-ratio:1 / 1" in css or "aspect-ratio:1/1" in css
    assert "object-fit:contain" in css
    assert "-webkit-line-clamp:2" in css
    assert "text-overflow:ellipsis" in css
    assert 'className="tpos-tile' in pos
    assert "{r.name}" in pos
    assert "{r.sku}" in pos
    assert "selling_price" in pos
    assert "stock_qty" in pos
    assert "addToCart(r)" in pos
    assert "kind === 'variant'" in pos
    assert "has_image" in pos
    assert "min-height:210px" not in css.split(".tpos-tile")[1][:800]
