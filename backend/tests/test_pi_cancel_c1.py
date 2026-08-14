"""Purchase invoice cancel (BR-6.5)."""

from __future__ import annotations

import pyotp
import pytest

from tests.conftest import auth_headers


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


async def _create_draft_pi(ac, headers, seed, *, name="Cancel PI Vendor"):
    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=headers,
        json={"name": name, "kind": "supplier", "email": "cancel-pi@example.com"},
    )
    assert supplier.status_code == 200, supplier.text
    created = await ac.post(
        "/api/v1/purchasing/invoices",
        headers=headers,
        json={
            "supplier_id": supplier.json()["data"]["id"],
            "items": [
                {
                    "product_id": seed["p1"].id,
                    "quantity": 2,
                    "unit_price": 10,
                    "tax_rate": 0,
                }
            ],
            "notes": "pi cancel test",
        },
    )
    assert created.status_code == 200, created.text
    return created.json()["data"]


@pytest.mark.asyncio
async def test_cancel_draft_purchase_invoice(client):
    ac, seed = client
    headers = await _admin(ac, seed)
    inv = await _create_draft_pi(ac, headers, seed, name="Draft Cancel PI")
    assert inv["status"] == "draft"
    assert inv.get("can_cancel") is True

    cancelled = await ac.post(
        f"/api/v1/purchasing/invoices/{inv['id']}/cancel", headers=headers
    )
    assert cancelled.status_code == 200, cancelled.text
    body = cancelled.json()["data"]
    assert body["status"] == "cancelled"
    assert body.get("can_cancel") is False

    # Idempotent cancel of already-cancelled
    again = await ac.post(
        f"/api/v1/purchasing/invoices/{inv['id']}/cancel", headers=headers
    )
    assert again.status_code == 200
    assert again.json()["data"]["status"] == "cancelled"


@pytest.mark.asyncio
async def test_cancel_approved_unpaid_purchase_invoice(client):
    ac, seed = client
    headers = await _admin(ac, seed)
    inv = await _create_draft_pi(ac, headers, seed, name="Unpaid Cancel PI")

    approved = await ac.post(
        f"/api/v1/purchasing/invoices/{inv['id']}/approve",
        headers=headers,
        json={},
    )
    assert approved.status_code == 200, approved.text
    body = approved.json()["data"]
    assert body["status"] in {"unpaid", "overdue"}
    assert body.get("can_cancel") is True
    assert float(body.get("paid_amount") or 0) == 0

    cancelled = await ac.post(
        f"/api/v1/purchasing/invoices/{inv['id']}/cancel", headers=headers
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["data"]["status"] == "cancelled"
    assert cancelled.json()["data"].get("can_cancel") is False


@pytest.mark.asyncio
async def test_cancel_blocked_when_partially_paid(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    inv = await _create_draft_pi(ac, headers, seed, name="Paid Block PI")

    approved = await ac.post(
        f"/api/v1/purchasing/invoices/{inv['id']}/approve",
        headers=headers,
        json={},
    )
    assert approved.status_code == 200, approved.text

    from app import models as m

    row = await db_session.get(m.PurchaseInvoice, inv["id"])
    row.paid_amount = 1
    row.status = "partial"
    await db_session.commit()

    detail = await ac.get(f"/api/v1/purchasing/invoices/{inv['id']}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["data"].get("can_cancel") is False

    blocked = await ac.post(
        f"/api/v1/purchasing/invoices/{inv['id']}/cancel", headers=headers
    )
    assert blocked.status_code == 409, blocked.text
