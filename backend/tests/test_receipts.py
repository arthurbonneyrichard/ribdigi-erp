from datetime import datetime

from app.receipts import (
    build_receipt_payload,
    render_thermal_html,
    render_thermal_text,
    to_thermal_pdf,
)


def _sample_receipt(*, store=None, party_id=None, party=None, extra_payload=None):
    payload = {
        "payment_method": "cash",
        "items": [
            {
                "name": "Bottled Water",
                "sku": "WAT-1",
                "quantity": 2,
                "unit_price": 10,
                "line_total": 20,
            }
        ],
    }
    if extra_payload:
        payload.update(extra_payload)
    tx = type(
        "Tx",
        (),
        {
            "id": "sale-1",
            "reference": "POS_SALE-1",
            "party_id": party_id,
            "subtotal": 20.0,
            "tax": 2.5,
            "total": 22.5,
            "session_id": None,
            "created_at": datetime(2026, 8, 8, 12, 0, 0),
            "payload": payload,
        },
    )()
    tenant = type(
        "T",
        (),
        {
            "company_name": "Demo Mart",
            "phone": "+233000000000",
            "email": "hello@demomart.example",
            "website": "www.demomart.example",
            "address": "12 High Street, Accra",
            "currency": "GHS",
        },
    )()
    return build_receipt_payload(
        tx=tx, tenant=tenant, cashier_name="Ama", store=store, party=party
    )


def test_thermal_text_contains_totals_and_company():
    receipt = _sample_receipt()
    text = render_thermal_text(receipt, paper="80mm")
    assert "Demo Mart" in text
    assert "12 High Street, Accra" in text
    assert "Tel: +233000000000" in text
    assert "hello@demomart.example" in text
    assert "POS_SALE-1" in text
    assert "Bottled Water" in text
    assert "TOTAL" in text
    assert "22.50" in text


def test_receipt_prefers_store_contact_and_location():
    store = type(
        "S",
        (),
        {
            "id": "store-1",
            "name": "East Legon Branch",
            "phone": "+233301112233",
            "address": "Boundary Rd, East Legon",
        },
    )()
    receipt = _sample_receipt(store=store)
    text = render_thermal_text(receipt, paper="80mm")
    assert receipt["store_name"] == "East Legon Branch"
    assert receipt["company_phone"] == "+233301112233"
    assert receipt["company_address"] == "Boundary Rd, East Legon"
    assert "East Legon Branch" in text
    assert "Boundary Rd, East Legon" in text
    assert "Tel: +233301112233" in text
    # Company email still shown when store has no email field.
    assert "hello@demomart.example" in text


def test_thermal_text_includes_optional_customer_name():
    receipt = _sample_receipt()
    receipt["customer_name"] = "Ama Mensah"
    text = render_thermal_text(receipt, paper="80mm")
    assert "Customer" in text
    assert "Ama Mensah" in text
    assert receipt["customer_name"] == "Ama Mensah"


def test_thermal_text_includes_cart_discount():
    receipt = _sample_receipt()
    receipt["discount_amount"] = 2.5
    receipt["total"] = 20.0
    text = render_thermal_text(receipt, paper="80mm")
    assert "Discount" in text
    assert "-2.50" in text


def test_thermal_text_lists_split_payments():
    receipt = _sample_receipt()
    receipt["payment_method"] = "split"
    receipt["payments"] = [
        {"payment_method": "cash", "amount": 10},
        {"payment_method": "card", "amount": 12.5},
    ]
    text = render_thermal_text(receipt, paper="80mm")
    assert "Payments" in text
    assert "CASH" in text
    assert "CARD" in text
    assert "10.00" in text
    assert "12.50" in text


def test_thermal_text_shows_credit_balance():
    receipt = _sample_receipt()
    receipt["payment_method"] = "credit"
    receipt["paid_amount"] = 5
    receipt["balance_due"] = 17.5
    receipt["payment_status"] = "partially_paid"
    receipt["invoice_number"] = "INV-1"
    text = render_thermal_text(receipt, paper="80mm")
    assert "Paid" in text
    assert "Balance due" in text
    assert "17.50" in text
    assert "PARTIALLY PAID" in text
    assert "INV-1" in text


def test_thermal_pdf_is_valid_pdf_bytes():
    receipt = _sample_receipt()
    pdf = to_thermal_pdf(receipt, paper="58mm")
    assert pdf.startswith(b"%PDF-1.4")
    assert b"%%EOF" in pdf
    assert len(pdf) > 200


def test_walk_in_receipt_ignores_leftover_customer_name():
    receipt = _sample_receipt(extra_payload={"customer_name": "Yesterday Kofi"})
    text = render_thermal_text(receipt, paper="80mm")
    html = render_thermal_html(receipt, paper="80mm")
    assert receipt["customer_name"] == "Walk-in"
    assert "Walk-in" in text
    assert "Yesterday Kofi" not in text
    assert "Walk-in" in html
    assert "Yesterday Kofi" not in html


def test_receipt_uses_selected_party_not_leftover_name():
    party = type("P", (), {"id": "cust-1", "name": "Ama Mensah"})()
    receipt = _sample_receipt(
        party_id="cust-1",
        party=party,
        extra_payload={"customer_name": "Yesterday Kofi"},
    )
    text = render_thermal_text(receipt, paper="80mm")
    assert receipt["customer_name"] == "Ama Mensah"
    assert "Ama Mensah" in text
    assert "Yesterday Kofi" not in text


def test_receipt_omits_payment_reference():
    receipt = _sample_receipt(
        extra_payload={
            "payment_method": "card",
            "payments": [
                {
                    "payment_method": "card",
                    "amount": 22.5,
                    "reference": "AUTH-99-SECRET",
                }
            ],
        }
    )
    text = render_thermal_text(receipt, paper="80mm")
    html = render_thermal_html(receipt, paper="80mm")
    pdf = to_thermal_pdf(receipt, paper="80mm")
    assert receipt["payments"] == [{"payment_method": "card", "amount": 22.5}]
    for blob in (text, html):
        assert "AUTH-99-SECRET" not in blob
        assert "payment reference" not in blob.lower()
    assert b"AUTH-99-SECRET" not in pdf
    assert "CARD" in text
    assert "22.50" in text
