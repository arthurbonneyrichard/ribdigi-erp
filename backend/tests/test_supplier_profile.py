"""Supplier profile (code/contacts/terms) and PO email/print."""

from __future__ import annotations

import pytest

from app.emailer import clear_dev_outbox, get_dev_outbox
from tests.conftest import auth_headers


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


@pytest.mark.asyncio
async def test_supplier_profile_contacts_history_and_deactivate(client):
    ac, seed = client
    headers = await _mgr(ac)

    created = await ac.post(
        "/api/v1/suppliers",
        headers=headers,
        json={
            "name": "Acme Supplies",
            "code": "ACM-01",
            "party_type": "distributor",
            "category": "General",
            "email": "orders@acme.example.com",
            "phone": "+233200000001",
            "address": "1 Warehouse Rd",
            "notes": "Net 30 preferred",
            "payment_terms_days": 30,
            "credit_limit": 5000,
            "contacts": [
                {
                    "name": "Ada Buyer",
                    "email": "ada@acme.example.com",
                    "phone": "+233200000002",
                    "is_primary": True,
                }
            ],
        },
    )
    assert created.status_code == 200, created.text
    supplier = created.json()["data"]
    assert supplier["code"] == "ACM-01"
    assert supplier["payment_terms_days"] == 30
    assert supplier["status"] == "active"
    assert len(supplier["contacts"]) == 1
    assert supplier["contacts"][0]["is_primary"] is True

    dup = await ac.post(
        "/api/v1/suppliers",
        headers=headers,
        json={"name": "Other", "code": "acm-01"},
    )
    assert dup.status_code == 409

    patched = await ac.patch(
        f"/api/v1/suppliers/{supplier['id']}",
        headers=headers,
        json={"payment_terms_days": 45, "notes": "Updated terms"},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["data"]["payment_terms_days"] == 45

    contact = await ac.post(
        f"/api/v1/suppliers/{supplier['id']}/contacts",
        headers=headers,
        json={"name": "Ben Ops", "email": "ben@acme.example.com", "is_primary": True},
    )
    assert contact.status_code == 200, contact.text
    detail = await ac.get(f"/api/v1/suppliers/{supplier['id']}", headers=headers)
    contacts = detail.json()["data"]["contacts"]
    assert len(contacts) == 2
    primaries = [c for c in contacts if c["is_primary"]]
    assert len(primaries) == 1
    assert primaries[0]["name"] == "Ben Ops"

    po = await ac.post(
        "/api/v1/purchasing/orders",
        headers=headers,
        json={
            "supplier_id": supplier["id"],
            "items": [{"product_id": seed["p1"].id, "quantity": 2, "unit_price": 10}],
        },
    )
    assert po.status_code == 200, po.text

    history = await ac.get(f"/api/v1/suppliers/{supplier['id']}/history", headers=headers)
    assert history.status_code == 200, history.text
    assert len(history.json()["data"]["orders"]) >= 1

    removed = await ac.delete(
        f"/api/v1/suppliers/{supplier['id']}/contacts/{contact.json()['data']['id']}",
        headers=headers,
    )
    assert removed.status_code == 200, removed.text

    deactivated = await ac.delete(f"/api/v1/suppliers/{supplier['id']}", headers=headers)
    assert deactivated.status_code == 200, deactivated.text
    assert deactivated.json()["data"]["status"] == "inactive"


@pytest.mark.asyncio
async def test_po_send_email_console_and_print(client, monkeypatch):
    ac, seed = client
    headers = await _mgr(ac)
    clear_dev_outbox()
    monkeypatch.setattr("app.emailer.settings.EMAIL_ENABLED", True)
    monkeypatch.setattr("app.emailer.settings.SMTP_HOST", "")
    monkeypatch.setattr("app.emailer.settings.SMTP_FROM_EMAIL", "noreply@localhost")

    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=headers,
        json={
            "name": "Email Supplier",
            "email": "po@supplier.example.com",
            "payment_terms_days": 14,
        },
    )
    assert supplier.status_code == 200, supplier.text
    supplier_id = supplier.json()["data"]["id"]

    po = await ac.post(
        "/api/v1/purchasing/orders",
        headers=headers,
        json={
            "supplier_id": supplier_id,
            "items": [{"product_id": seed["p1"].id, "quantity": 3, "unit_price": 4}],
        },
    )
    assert po.status_code == 200, po.text
    po_id = po.json()["data"]["id"]
    po_number = po.json()["data"]["po_number"]

    printed = await ac.get(f"/api/v1/purchasing/orders/{po_id}/print", headers=headers)
    assert printed.status_code == 200, printed.text
    text = printed.json()["data"]["text"]
    assert po_number in text
    assert "Email Supplier" in text
    assert "Alpha Co" in text

    sent = await ac.post(
        f"/api/v1/purchasing/orders/{po_id}/send",
        headers=headers,
        params={"email": True},
    )
    assert sent.status_code == 200, sent.text
    data = sent.json()["data"]
    assert data["status"] == "sent"
    assert data["emailed_to"] == "po@supplier.example.com"
    assert data["sent_at"]
    assert data["delivery"]["mode"] == "console"
    assert data["delivery"]["sent"] is True
    assert data["due_date"]

    out = get_dev_outbox()
    assert out and po_number in out[0]["subject"]
    assert out[0]["to"] == ["po@supplier.example.com"]


@pytest.mark.asyncio
async def test_po_send_without_email_when_no_recipient(client):
    ac, seed = client
    headers = await _mgr(ac)

    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=headers,
        json={"name": "No Email Supplier"},
    )
    supplier_id = supplier.json()["data"]["id"]
    po = await ac.post(
        "/api/v1/purchasing/orders",
        headers=headers,
        json={
            "supplier_id": supplier_id,
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 1}],
        },
    )
    po_id = po.json()["data"]["id"]

    sent = await ac.post(f"/api/v1/purchasing/orders/{po_id}/send", headers=headers)
    assert sent.status_code == 200, sent.text
    data = sent.json()["data"]
    assert data["status"] == "sent"
    assert data["emailed_to"] is None
    assert "delivery" not in data

    forced = await ac.post(
        "/api/v1/purchasing/orders",
        headers=headers,
        json={
            "supplier_id": supplier_id,
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 1}],
        },
    )
    forced_id = forced.json()["data"]["id"]
    bad = await ac.post(
        f"/api/v1/purchasing/orders/{forced_id}/send",
        headers=headers,
        params={"email": True},
    )
    assert bad.status_code == 400
