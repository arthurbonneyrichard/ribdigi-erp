"""Purchase order cancel (BR-6.3)."""

from __future__ import annotations

import pyotp
import pytest

from app import models as m
from tests.conftest import auth_headers


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


async def _supplier_and_po(ac, headers, seed, *, notes="cancel test"):
    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=headers,
        json={"name": f"Cancel Vendor {notes}", "kind": "supplier", "email": "cancel-v@example.com"},
    )
    assert supplier.status_code == 200, supplier.text
    created = await ac.post(
        "/api/v1/purchasing/orders",
        headers=headers,
        json={
            "supplier_id": supplier.json()["data"]["id"],
            "notes": notes,
            "items": [{"product_id": seed["p1"].id, "quantity": 2, "unit_price": 5}],
        },
    )
    assert created.status_code == 200, created.text
    return created.json()["data"]


@pytest.mark.asyncio
async def test_cancel_draft_po(client):
    ac, seed = client
    headers = await _admin(ac, seed)
    po = await _supplier_and_po(ac, headers, seed, notes="draft cancel")
    assert po["status"] == "draft"
    assert po.get("can_cancel") is True

    cancelled = await ac.post(
        f"/api/v1/purchasing/orders/{po['id']}/cancel",
        headers=headers,
        json={"reason": "Supplier unavailable — draft cancel"},
    )
    assert cancelled.status_code == 200, cancelled.text
    body = cancelled.json()["data"]
    assert body["status"] == "cancelled"
    assert body.get("can_cancel") is False
    assert body.get("can_amend") is False
    assert "Cancel: Supplier unavailable — draft cancel" in (body.get("notes") or "")

    again = await ac.post(
        f"/api/v1/purchasing/orders/{po['id']}/cancel",
        headers=headers,
        json={"reason": "retry"},
    )
    assert again.status_code == 409


@pytest.mark.asyncio
async def test_cancel_sent_po(client):
    ac, seed = client
    headers = await _admin(ac, seed)
    po = await _supplier_and_po(ac, headers, seed, notes="sent cancel")

    sent = await ac.post(
        f"/api/v1/purchasing/orders/{po['id']}/send", headers=headers
    )
    assert sent.status_code == 200, sent.text
    assert sent.json()["data"]["status"] == "sent"
    assert sent.json()["data"].get("can_cancel") is True

    cancelled = await ac.post(
        f"/api/v1/purchasing/orders/{po['id']}/cancel",
        headers=headers,
        json={"reason": "Order duplicate — sent cancel"},
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["data"]["status"] == "cancelled"
    assert "Cancel: Order duplicate — sent cancel" in (
        cancelled.json()["data"].get("notes") or ""
    )


@pytest.mark.asyncio
async def test_cancel_blocked_after_grn_receipt(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    po = await _supplier_and_po(ac, headers, seed, notes="receipt block")

    row = await db_session.get(m.PurchaseOrder, po["id"])
    row.status = "sent"
    await db_session.commit()

    grn = await ac.post(
        "/api/v1/purchasing/grn",
        headers=headers,
        json={
            "purchase_order_id": po["id"],
            "items": [
                {
                    "po_item_id": po["items"][0]["id"],
                    "received_qty": 1,
                    "accepted_qty": 1,
                }
            ],
        },
    )
    assert grn.status_code == 200, grn.text

    detail = await ac.get(f"/api/v1/purchasing/orders/{po['id']}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["data"].get("can_cancel") is False

    blocked = await ac.post(
        f"/api/v1/purchasing/orders/{po['id']}/cancel",
        headers=headers,
        json={"reason": "should fail after GRN"},
    )
    assert blocked.status_code == 409, blocked.text
    assert "received" in blocked.json()["detail"].lower()
