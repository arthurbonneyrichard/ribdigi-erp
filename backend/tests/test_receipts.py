from datetime import datetime

from app.receipts import build_receipt_payload, render_thermal_text, to_thermal_pdf


def _sample_receipt():
    tx = type(
        "Tx",
        (),
        {
            "id": "sale-1",
            "reference": "POS_SALE-1",
            "subtotal": 20.0,
            "tax": 2.5,
            "total": 22.5,
            "created_at": datetime(2026, 8, 8, 12, 0, 0),
            "payload": {
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
            },
        },
    )()
    tenant = type(
        "T",
        (),
        {
            "company_name": "Demo Mart",
            "phone": "+233000000000",
            "address": "Accra",
            "currency": "GHS",
        },
    )()
    return build_receipt_payload(tx=tx, tenant=tenant, cashier_name="Ama")


def test_thermal_text_contains_totals_and_company():
    receipt = _sample_receipt()
    text = render_thermal_text(receipt, paper="80mm")
    assert "Demo Mart" in text
    assert "POS_SALE-1" in text
    assert "Bottled Water" in text
    assert "TOTAL" in text
    assert "22.50" in text


def test_thermal_text_includes_optional_customer_name():
    receipt = _sample_receipt()
    receipt["customer_name"] = "Ama Mensah"
    text = render_thermal_text(receipt, paper="80mm")
    assert "Customer" in text
    assert "Ama Mensah" in text
    assert receipt["customer_name"] == "Ama Mensah"


def test_thermal_pdf_is_valid_pdf_bytes():
    receipt = _sample_receipt()
    pdf = to_thermal_pdf(receipt, paper="58mm")
    assert pdf.startswith(b"%PDF-1.4")
    assert b"%%EOF" in pdf
    assert len(pdf) > 200
