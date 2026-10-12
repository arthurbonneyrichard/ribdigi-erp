"""POS till checkout markup: no payment reference, no new-customer create, split amounts."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "frontend/app/(dashboard)/pos/page.tsx"


def test_pos_till_omits_payment_reference_and_new_customer():
    page = PAGE.read_text(encoding="utf-8")
    assert 'aria-label="POS payment reference"' not in page
    assert "Payment reference" not in page
    assert "paymentReference" not in page
    assert "New customer" not in page
    assert 'aria-label="Save new customer"' not in page
    assert 'aria-label="Create POS customer name"' not in page
    assert "createPosCustomer" not in page
    assert "POS customer" in page


def test_pos_till_split_amounts_are_present():
    page = PAGE.read_text(encoding="utf-8")
    assert 'aria-label="POS split tender"' in page
    assert 'aria-label="POS payment method"' in page
    assert 'aria-label="POS cash tender"' in page
    assert 'aria-label="POS card tender"' in page
    assert 'aria-label="POS split second method"' in page
    assert "Amount due" in page
    assert "Cash amount" in page
    assert "must add up to the amount due" in page
    for method in ("card", "mobile_money", "bank_transfer"):
        assert method in page
    assert "does not charge a phone" in page
