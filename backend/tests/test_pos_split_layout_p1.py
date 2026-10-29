"""POS split workspace: cart left, catalog right, categories, keypad, receipt preview."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _css() -> str:
    return (ROOT / "frontend/app/globals.css").read_text(encoding="utf-8")


def _pos() -> str:
    return (ROOT / "frontend/app/(dashboard)/pos/page.tsx").read_text(encoding="utf-8")


def _pos_css() -> str:
    return (ROOT / "frontend/app/(dashboard)/pos/pos-modern.css").read_text(encoding="utf-8")


def test_pos_split_layout_catalog_left_cart_right():
    css = _css()
    pos = _pos()
    compact = css.replace(" ", "").replace("\n", "")
    assert 'grid-template-areas:"catalogcart"' in compact
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
    # Pay charges; after the sale the done panel offers Print receipt and New sale.
    assert 'aria-label="Charge"' in pos
    assert 'aria-label="Print receipt"' in pos
    assert "addToCart(r)" in pos
    assert "{r.sku}" in pos
    assert "client_request_id" in pos
    assert "enqueueOfflineSale" in pos
    assert "minmax(300px,400px)" not in compact
    assert "height:85vh" not in compact
    assert "100svh" in compact
    assert "minmax(0,min(400px,38vw))" in compact
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
    assert 'grid-template-areas:"catalogcart"' in compact
    assert "minmax(300px,400px)" not in compact
    assert "height:85vh" not in compact
    assert "100svh" in compact
    assert "minmax(0,min(400px,38vw))" in compact
    assert "offline_complete_claimed" not in pos


def test_pos_pay_keypad_tap_targets():
    css = _css()
    pos = _pos()
    pos_css = _pos_css()
    compact_pos_css = pos_css.replace(" ", "").replace("\n", "").replace("\r", "")
    compact_css = css.replace(" ", "").replace("\n", "").replace("\r", "")
    assert "const [keypadOpen, setKeypadOpen] = useState(false)" in pos
    assert "function hideKeypad(" in pos
    assert "function toggleKeypad(" in pos
    assert "onClick={toggleKeypad}" in pos
    assert "aria-label={keypadOpen ? 'Hide keypad' : 'Show keypad'}" in pos
    assert pos.count("{keypadOpen ? 'Hide keypad' : 'Show keypad'}") == 1
    assert 'className="tpos-keypad-toggle-verb"' in pos
    assert "{keypadOpen ? 'Hide' : 'Show'}" in pos
    assert 'className="tpos-keypad-toggle-noun"' in pos
    assert ">keypad</span>" in pos
    assert 'className="tpos-pay-row"' in pos
    assert 'aria-label="Charge"' in pos
    assert pos.find('aria-label="Charge"') < pos.find("onClick={toggleKeypad}")
    assert 'className="pos-pay-keys"' not in pos
    assert 'className="pos-keypad-dock"' in pos
    assert 'aria-label="POS keypad"' in pos
    assert "{payAsReprint || !keypadOpen ? null : (" in pos
    assert "function openKeypad(" in pos
    assert "openKeypad('discount')" in pos
    assert "openKeypad('coupon')" in pos
    assert "if (keypadField === 'discount')" in pos
    assert "['1', '2', '3', '4', '5', '6', '7', '8', '9', '.', '0', '⌫']" in pos
    assert "const COUPON_LETTER_KEYS = [" in pos
    assert "'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I'," in pos
    assert "'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z', 'CLR'," in pos
    assert "keypadField === 'coupon'" in pos
    assert 'aria-label="POS coupon letters"' in pos
    assert 'aria-label={key === \'CLR\' ? \'Clear coupon code\' : `Keypad ${key}`}' in pos
    assert "key === 'CLR' || key === 'Clear'" in pos
    assert "key === 'C' && keypadField !== 'coupon'" in pos
    assert ".pos-pay-keys" not in pos_css
    assert ".pos-keypad-dock" in pos_css
    assert ".tpos-pay-row.tpos-keypad-toggle{" in compact_pos_css
    assert "height:52px;min-height:52px" in compact_pos_css
    assert ".tpos-cart-actions button.tpos-btn.tpos-keypad-toggle{" not in compact_pos_css
    assert ".tpos-cart-actions button.tpos-keypad-toggle{" not in compact_pos_css
    assert ".tpos-cart-actions.tpos-keypad-toggle{" not in compact_css
    assert ".pos-foot-sum.tpos-pay-rowbutton.tpos-btn-pay" in compact_pos_css
    toggle_rules = compact_pos_css.split(".tpos-pay-row.tpos-keypad-toggle{")[1:]
    assert toggle_rules
    for chunk in toggle_rules:
        toggle_height = chunk.split("}")[0]
        if "height:" not in toggle_height:
            continue
        assert "height:52px;min-height:52px" in toggle_height
        assert "width:3rem" not in toggle_height
        assert "max-width:3rem" not in toggle_height
        assert "min-width:4.75rem" in toggle_height
        assert "font-size:12px" in toggle_height
        assert "font-weight:800" in toggle_height or "text-transform:uppercase" in toggle_height
        assert "height:32px" not in toggle_height
        assert "height:36px" not in toggle_height
    label_css = compact_pos_css.split(".tpos-pay-row.tpos-keypad-toggle-verb,.main.tpos.pos-ui.tpos-pay-row.tpos-keypad-toggle-noun{")
    if len(label_css) < 2:
        label_css = compact_pos_css.split(".tpos-keypad-toggle-noun{")
    assert len(label_css) >= 2
    label_rule = label_css[1].split("}")[0]
    assert "white-space:nowrap" in label_rule
    assert "text-transform:uppercase" in label_rule
    assert "font-weight:800" in label_rule
    assert ".pos-keypad-dock.tpos-keypad{display:grid;grid-template-columns:repeat(3,minmax(0,1fr))" in compact_pos_css
    assert ".pos-keypad-dock.tpos-keypad.tpos-key{height:auto;min-height:56px" in compact_pos_css
    assert ".pos-keypad-dock.tpos-keypad-letters{display:grid;grid-template-columns:repeat(9,minmax(0,1fr))" in compact_pos_css
    assert ".tpos-keypad-letters.tpos-key{min-height:36px" in compact_pos_css
    assert "flex-direction:column" not in compact_pos_css.split(".pos-pay-methods{")[1].split("}")[0]
    assert ".tpos-key{min-height:56px" in compact_css
    assert ".greet-time{--greet-digit-size:3rem}" in compact_css
    assert ".greet-time{--greet-digit-size:2rem}" not in compact_css
    assert "Discount, coupon and receipt options" in pos
    assert "pos-pay-methods" in pos
    assert "['cash', 'Cash']" in pos
    assert "offline_complete_claimed" not in pos


def test_pos_cash_received_starts_empty():
    pos = _pos()
    assert "const [cashTender, setCashTender] = useState('')" in pos
    assert 'aria-label="Cash received"' in pos
    assert "placeholder={cartTotal.toFixed(2)}" not in pos
    assert "placeholder={cartTotal" not in pos
    cash_block = pos.split('aria-label="Cash received"')[0].rsplit("<AmountField", 1)[1]
    assert 'placeholder=""' in cash_block
    assert "cashReceivedEntered" in pos
    assert "payingCash && cashReceivedEntered && cashTenderAmount > cartTotal" in pos
    assert "setCashTender('')" in pos
    assert "offline_complete_claimed" not in pos

