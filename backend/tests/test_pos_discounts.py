"""POS line and cart discount validation helpers (unit-level)."""


def apply_line_and_cart_discounts(
    *,
    qty: float,
    unit_price: float,
    line_discount: float,
    cart_discount: float,
    tax_rate_pct: float = 0,
):
    gross = round(qty * unit_price, 2)
    if line_discount < 0:
        raise ValueError("Line discount must be >= 0")
    if line_discount > gross:
        raise ValueError("Line discount exceeds line amount")
    taxable = round(gross - line_discount, 2)
    tax = round(taxable * (tax_rate_pct / 100), 2)
    subtotal = taxable
    max_cart = round(subtotal + tax, 2)
    if cart_discount < 0:
        raise ValueError("discount_amount must be >= 0")
    if cart_discount > max_cart:
        raise ValueError("Cart discount exceeds sale total")
    total = round(subtotal + tax - cart_discount, 2)
    return {
        "subtotal": subtotal,
        "tax": tax,
        "line_discounts": round(line_discount, 2),
        "discount_amount": round(cart_discount, 2),
        "total": total,
    }


def test_line_discount_reduces_taxable_base():
    result = apply_line_and_cart_discounts(
        qty=2, unit_price=10, line_discount=2, cart_discount=0, tax_rate_pct=15
    )
    assert result["subtotal"] == 18.0
    assert result["tax"] == 2.7
    assert result["total"] == 20.7
    assert result["line_discounts"] == 2


def test_cart_discount_applied_after_tax():
    result = apply_line_and_cart_discounts(
        qty=1, unit_price=10, line_discount=0, cart_discount=1.5, tax_rate_pct=15
    )
    assert result["subtotal"] == 10.0
    assert result["tax"] == 1.5
    assert result["discount_amount"] == 1.5
    assert result["total"] == 10.0


def test_line_discount_cannot_exceed_line():
    try:
        apply_line_and_cart_discounts(qty=1, unit_price=5, line_discount=6, cart_discount=0)
        assert False, "expected error"
    except ValueError as exc:
        assert "exceeds line" in str(exc)
