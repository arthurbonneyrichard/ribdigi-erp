"""Sales invoice email to customer (BR-7.4)."""

from __future__ import annotations

import pyotp
import pytest

from app.emailer import clear_dev_outbox, get_dev_outbox, render_sales_invoice_bodies
from app.rbac import permissions_for_role
from app.security import hash_password
from app import models as m
from tests.conftest import auth_headers


def test_render_sales_invoice_bodies_includes_total():
    text, html = render_sales_invoice_bodies(
        company_name="Acme",
        currency="GHS",
        customer_name="Buyer Co",
        invoice={
            "invoice_number": "INV-1",
            "subtotal": 100,
            "tax_amount": 15,
            "discount_amount": 0,
            "total_amount": 115,
            "paid_amount": 0,
            "balance_due": 115,
            "due_date": "2026-08-20",
            "items": [
                {
                    "product_id": "p1",
                    "quantity": 2,
                    "unit_price": 50,
                    "tax_rate": 15,
                    "line_total": 115,
                }
            ],
        },
    )
    assert "INV-1" in text and "115.00" in text
    assert "Buyer Co" in html and "Acme" in html
    assert "Due date" in text or "Due" in html


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_send_invoice_email_console_and_resend(client, db_session, monkeypatch):
    ac, seed = client
    admin = await _super(ac, seed)

    monkeypatch.setattr("app.emailer.settings.EMAIL_ENABLED", True)
    monkeypatch.setattr("app.emailer.settings.SMTP_HOST", "")
    monkeypatch.setattr("app.emailer.settings.SMTP_FROM_EMAIL", "noreply@localhost")
    clear_dev_outbox()

    customer = await ac.post(
        "/api/v1/customers",
        headers=admin,
        json={"name": "Email Buyer", "kind": "customer", "email": "buyer@example.com"},
    )
    assert customer.status_code == 200, customer.text
    customer_id = customer.json()["data"]["id"]

    created = await ac.post(
        "/api/v1/sales/invoices",
        headers=admin,
        json={
            "customer_id": customer_id,
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 10}],
            "notes": "Net 14",
        },
    )
    assert created.status_code == 200, created.text
    inv_id = created.json()["data"]["id"]
    assert created.json()["data"]["status"] == "draft"

    # Draft cannot be emailed
    draft_send = await ac.post(f"/api/v1/sales/invoices/{inv_id}/send", headers=admin)
    assert draft_send.status_code == 409

    posted = await ac.post(f"/api/v1/sales/invoices/{inv_id}/post", headers=admin)
    assert posted.status_code == 200, posted.text
    assert posted.json()["data"]["status"] == "posted"

    sent = await ac.post(f"/api/v1/sales/invoices/{inv_id}/send", headers=admin)
    assert sent.status_code == 200, sent.text
    body = sent.json()["data"]
    assert body["status"] == "posted"
    assert body["emailed_to"] == "buyer@example.com"
    assert body["emailed_at"]
    assert body["delivery"]["mode"] == "console"
    assert body["delivery"]["to"] == "buyer@example.com"
    out = get_dev_outbox()
    assert out and "Invoice" in out[0]["subject"]
    assert out[0]["to"] == ["buyer@example.com"]
    assert "Net 14" in out[0]["text_body"]

    # Resend with override — status stays posted
    clear_dev_outbox()
    resent = await ac.post(
        f"/api/v1/sales/invoices/{inv_id}/send",
        headers=admin,
        params={"to": "alt-buyer@example.com"},
    )
    assert resent.status_code == 200, resent.text
    assert resent.json()["data"]["status"] == "posted"
    assert resent.json()["data"]["emailed_to"] == "alt-buyer@example.com"
    assert get_dev_outbox()[0]["to"] == ["alt-buyer@example.com"]


@pytest.mark.asyncio
async def test_send_invoice_requires_customer_email(client, db_session, monkeypatch):
    ac, seed = client
    admin = await _super(ac, seed)
    monkeypatch.setattr("app.emailer.settings.EMAIL_ENABLED", True)
    monkeypatch.setattr("app.emailer.settings.SMTP_HOST", "")

    customer = await ac.post(
        "/api/v1/customers",
        headers=admin,
        json={"name": "No Email Buyer", "kind": "customer"},
    )
    assert customer.status_code == 200, customer.text
    created = await ac.post(
        "/api/v1/sales/invoices",
        headers=admin,
        json={
            "customer_id": customer.json()["data"]["id"],
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 5}],
        },
    )
    assert created.status_code == 200, created.text
    inv_id = created.json()["data"]["id"]
    posted = await ac.post(f"/api/v1/sales/invoices/{inv_id}/post", headers=admin)
    assert posted.status_code == 200, posted.text

    missing = await ac.post(f"/api/v1/sales/invoices/{inv_id}/send", headers=admin)
    assert missing.status_code == 400
    assert "email" in missing.json()["detail"].lower()
    got = await ac.get(f"/api/v1/sales/invoices/{inv_id}", headers=admin)
    assert got.json()["data"]["status"] == "posted"
    assert not got.json()["data"].get("emailed_at")


@pytest.mark.asyncio
async def test_send_invoice_email_disabled(client, db_session, monkeypatch):
    ac, seed = client
    admin = await _super(ac, seed)
    monkeypatch.setattr("app.emailer.settings.EMAIL_ENABLED", False)

    customer = await ac.post(
        "/api/v1/customers",
        headers=admin,
        json={"name": "Disabled Mail Buyer", "kind": "customer", "email": "b@example.com"},
    )
    created = await ac.post(
        "/api/v1/sales/invoices",
        headers=admin,
        json={
            "customer_id": customer.json()["data"]["id"],
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 5}],
        },
    )
    inv_id = created.json()["data"]["id"]
    posted = await ac.post(f"/api/v1/sales/invoices/{inv_id}/post", headers=admin)
    assert posted.status_code == 200, posted.text

    disabled = await ac.post(f"/api/v1/sales/invoices/{inv_id}/send", headers=admin)
    assert disabled.status_code == 503
    got = await ac.get(f"/api/v1/sales/invoices/{inv_id}", headers=admin)
    assert got.json()["data"]["status"] == "posted"
    assert not got.json()["data"].get("emailed_at")
