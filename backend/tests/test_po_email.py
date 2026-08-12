"""Purchase order email to supplier (BR-6.3)."""

from __future__ import annotations

import pyotp
import pytest

from app.emailer import clear_dev_outbox, get_dev_outbox, render_purchase_order_bodies
from app.rbac import permissions_for_role
from app.security import hash_password
from app import models as m
from tests.conftest import auth_headers


def test_render_purchase_order_bodies_includes_total():
    text, html = render_purchase_order_bodies(
        company_name="Acme",
        currency="GHS",
        supplier_name="Vendor Co",
        purchase_order={
            "po_number": "PO-1",
            "subtotal": 100,
            "tax_amount": 15,
            "total_amount": 115,
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
    assert "PO-1" in text and "115.00" in text
    assert "Vendor Co" in html and "Acme" in html


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


async def _seed_io(db_session, seed):
    user = m.User(
        tenant_id=seed["t1"].id,
        email="io-po-email@alpha.example.com",
        full_name="IO PO Email",
        password_hash=hash_password("SecurePass123!"),
        role="inventory_officer",
        email_verified=True,
        permissions=permissions_for_role("inventory_officer"),
        totp_enabled=False,
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest.mark.asyncio
async def test_send_po_email_console_and_resend(client, db_session, monkeypatch):
    ac, seed = client
    await _seed_io(db_session, seed)
    admin = await _super(ac, seed)
    io = await auth_headers(ac, email="io-po-email@alpha.example.com", tenant_slug="alpha")

    monkeypatch.setattr("app.emailer.settings.EMAIL_ENABLED", True)
    monkeypatch.setattr("app.emailer.settings.SMTP_HOST", "")
    monkeypatch.setattr("app.emailer.settings.SMTP_FROM_EMAIL", "noreply@localhost")
    clear_dev_outbox()

    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=admin,
        json={"name": "Email Vendor", "kind": "supplier", "email": "vendor@example.com"},
    )
    assert supplier.status_code == 200, supplier.text
    supplier_id = supplier.json()["data"]["id"]

    created = await ac.post(
        "/api/v1/purchasing/orders",
        headers=io,
        json={
            "supplier_id": supplier_id,
            "items": [{"product_id": seed["p1"].id, "quantity": 2, "unit_price": 5}],
            "notes": "Please ship ASAP",
        },
    )
    assert created.status_code == 200, created.text
    po_id = created.json()["data"]["id"]
    assert created.json()["data"]["status"] == "draft"

    sent = await ac.post(f"/api/v1/purchasing/orders/{po_id}/send", headers=io)
    assert sent.status_code == 200, sent.text
    body = sent.json()["data"]
    assert body["status"] == "sent"
    assert body["emailed_to"] == "vendor@example.com"
    assert body["emailed_at"]
    assert body["delivery"]["mode"] == "console"
    assert body["delivery"]["to"] == "vendor@example.com"
    out = get_dev_outbox()
    assert out and "PO-" in out[0]["subject"]
    assert out[0]["to"] == ["vendor@example.com"]
    assert "Please ship ASAP" in out[0]["text_body"]

    # Resend with override address
    clear_dev_outbox()
    resent = await ac.post(
        f"/api/v1/purchasing/orders/{po_id}/send",
        headers=io,
        params={"to": "alt@example.com"},
    )
    assert resent.status_code == 200, resent.text
    assert resent.json()["data"]["emailed_to"] == "alt@example.com"
    assert get_dev_outbox()[0]["to"] == ["alt@example.com"]


@pytest.mark.asyncio
async def test_send_po_requires_supplier_email(client, db_session, monkeypatch):
    ac, seed = client
    await _seed_io(db_session, seed)
    admin = await _super(ac, seed)
    io = await auth_headers(ac, email="io-po-email@alpha.example.com", tenant_slug="alpha")
    monkeypatch.setattr("app.emailer.settings.EMAIL_ENABLED", True)
    monkeypatch.setattr("app.emailer.settings.SMTP_HOST", "")

    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=admin,
        json={"name": "No Email Vendor", "kind": "supplier"},
    )
    assert supplier.status_code == 200, supplier.text
    created = await ac.post(
        "/api/v1/purchasing/orders",
        headers=io,
        json={
            "supplier_id": supplier.json()["data"]["id"],
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 3}],
        },
    )
    assert created.status_code == 200, created.text
    po_id = created.json()["data"]["id"]

    missing = await ac.post(f"/api/v1/purchasing/orders/{po_id}/send", headers=io)
    assert missing.status_code == 400
    assert "email" in missing.json()["detail"].lower()
    # Status stays draft on failure
    got = await ac.get(f"/api/v1/purchasing/orders/{po_id}", headers=io)
    assert got.json()["data"]["status"] == "draft"


@pytest.mark.asyncio
async def test_send_po_email_disabled(client, db_session, monkeypatch):
    ac, seed = client
    await _seed_io(db_session, seed)
    admin = await _super(ac, seed)
    io = await auth_headers(ac, email="io-po-email@alpha.example.com", tenant_slug="alpha")
    monkeypatch.setattr("app.emailer.settings.EMAIL_ENABLED", False)

    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=admin,
        json={"name": "Disabled Mail Vendor", "kind": "supplier", "email": "v@example.com"},
    )
    created = await ac.post(
        "/api/v1/purchasing/orders",
        headers=io,
        json={
            "supplier_id": supplier.json()["data"]["id"],
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 3}],
        },
    )
    po_id = created.json()["data"]["id"]
    disabled = await ac.post(f"/api/v1/purchasing/orders/{po_id}/send", headers=io)
    assert disabled.status_code == 503
    got = await ac.get(f"/api/v1/purchasing/orders/{po_id}", headers=io)
    assert got.json()["data"]["status"] == "draft"
