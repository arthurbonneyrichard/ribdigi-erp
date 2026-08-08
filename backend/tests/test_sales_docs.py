from app.sales_docs import RETURN_REASONS
from app.sales import invoice_payment_status
from app.emailer import render_quotation_bodies, clear_dev_outbox, get_dev_outbox
import pytest


def test_return_reasons_cover_common_cases():
    for reason in ("damaged", "wrong_item", "defective", "customer_change", "other"):
        assert reason in RETURN_REASONS


def test_invoice_status_after_return_credit():
    # return credited against open invoice behaves like payment
    assert invoice_payment_status(100, 40) == "partial"
    assert invoice_payment_status(100, 100) == "paid"


def test_quotation_status_machine_values():
    allowed = {"draft", "sent", "accepted", "rejected", "expired", "converted"}
    assert "draft" in allowed and "converted" in allowed


def test_order_status_machine_values():
    allowed = {"draft", "confirmed", "invoiced", "cancelled"}
    assert allowed.issuperset({"draft", "confirmed", "invoiced"})


def test_render_quotation_bodies_includes_total():
    text, html = render_quotation_bodies(
        company_name="Acme",
        currency="GHS",
        customer_name="Buyer",
        quotation={
            "quotation_number": "QT-1",
            "subtotal": 100,
            "tax_amount": 15,
            "discount_amount": 0,
            "total_amount": 115,
            "valid_until": "2026-08-20",
            "items": [
                {
                    "product_id": "p1",
                    "quantity": 2,
                    "unit_price": 50,
                    "line_total": 100,
                }
            ],
        },
    )
    assert "QT-1" in text and "115.00" in text
    assert "Acme" in html and "Buyer" in html


@pytest.mark.asyncio
async def test_send_quotation_email_console(monkeypatch):
    from app import emailer

    clear_dev_outbox()
    monkeypatch.setattr("app.emailer.settings.EMAIL_ENABLED", True)
    monkeypatch.setattr("app.emailer.settings.SMTP_HOST", "")
    monkeypatch.setattr("app.emailer.settings.SMTP_FROM_EMAIL", "noreply@localhost")
    result = await emailer.send_quotation_email(
        to="buyer@example.com",
        company_name="Acme",
        currency="GHS",
        customer_name="Buyer",
        quotation={
            "quotation_number": "QT-9",
            "subtotal": 10,
            "tax_amount": 0,
            "discount_amount": 0,
            "total_amount": 10,
            "items": [],
        },
    )
    assert result.sent and result.mode == "console"
    out = get_dev_outbox()
    assert out and "QT-9" in out[0]["subject"]
    assert out[0]["to"] == ["buyer@example.com"]
