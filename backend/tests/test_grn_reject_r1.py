"""GRN rejected/damaged goods with reason (BR-6.4)."""

from __future__ import annotations

import pyotp
import pytest

from app import models as m
from app.rbac import permissions_for_role
from app.security import hash_password
from tests.conftest import auth_headers


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


async def _seed_io(db_session, seed):
    user = m.User(
        tenant_id=seed["t1"].id,
        email="io-grn-reject@alpha.example.com",
        full_name="IO GRN Reject",
        password_hash=hash_password("SecurePass123!"),
        role="inventory_officer",
        email_verified=True,
        permissions=permissions_for_role("inventory_officer"),
        totp_enabled=False,
    )
    db_session.add(user)
    await db_session.commit()
    return user


async def _sent_po(ac, db_session, *, admin, io, seed, qty: float = 10):
    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=admin,
        json={"name": "Reject Vendor", "kind": "supplier", "email": "reject-v@example.com"},
    )
    supplier_id = supplier.json()["data"]["id"]
    created = await ac.post(
        "/api/v1/purchasing/orders",
        headers=io,
        json={
            "supplier_id": supplier_id,
            "items": [{"product_id": seed["p1"].id, "quantity": qty, "unit_price": 3}],
        },
    )
    assert created.status_code == 200, created.text
    po_id = created.json()["data"]["id"]
    po_item_id = created.json()["data"]["items"][0]["id"]
    po = await db_session.get(m.PurchaseOrder, po_id)
    po.status = "sent"
    await db_session.commit()
    return po_id, po_item_id


@pytest.mark.asyncio
async def test_grn_reject_requires_reason_and_stocks_accepted_only(client, db_session):
    ac, seed = client
    await _seed_io(db_session, seed)
    admin = await _super(ac, seed)
    io = await auth_headers(ac, email="io-grn-reject@alpha.example.com", tenant_slug="alpha")
    po_id, po_item_id = await _sent_po(ac, db_session, admin=admin, io=io, seed=seed, qty=10)

    product = await db_session.get(m.Product, seed["p1"].id)
    stock_before = float(product.stock_qty or 0)

    missing_reason = await ac.post(
        "/api/v1/purchasing/grn",
        headers=io,
        json={
            "purchase_order_id": po_id,
            "items": [
                {
                    "po_item_id": po_item_id,
                    "received_qty": 10,
                    "accepted_qty": 8,
                    "rejected_qty": 2,
                }
            ],
        },
    )
    assert missing_reason.status_code == 400
    assert "rejection_reason" in missing_reason.text.lower()

    ok = await ac.post(
        "/api/v1/purchasing/grn",
        headers=io,
        json={
            "purchase_order_id": po_id,
            "items": [
                {
                    "po_item_id": po_item_id,
                    "received_qty": 10,
                    "accepted_qty": 8,
                    "rejected_qty": 2,
                    "rejection_reason": "Damaged packaging",
                }
            ],
        },
    )
    assert ok.status_code == 200, ok.text
    data = ok.json()["data"]
    assert data["items"][0]["accepted_qty"] == 8.0
    assert data["items"][0]["rejected_qty"] == 2.0
    assert data["items"][0]["rejection_reason"] == "Damaged packaging"

    await db_session.refresh(product)
    assert float(product.stock_qty or 0) == pytest.approx(stock_before + 8.0)

    po = await ac.get(f"/api/v1/purchasing/orders/{po_id}", headers=io)
    assert po.status_code == 200
    line = po.json()["data"]["items"][0]
    assert line["received_qty"] == 10.0
    assert line["outstanding_qty"] == 0.0
    assert po.json()["data"]["status"] == "received"


@pytest.mark.asyncio
async def test_grn_reject_inferred_from_accepted_shortfall(client, db_session):
    ac, seed = client
    await _seed_io(db_session, seed)
    admin = await _super(ac, seed)
    io = await auth_headers(ac, email="io-grn-reject@alpha.example.com", tenant_slug="alpha")
    po_id, po_item_id = await _sent_po(ac, db_session, admin=admin, io=io, seed=seed, qty=5)

    # rejected_qty omitted; accepted < received → reject remainder, still needs reason
    missing = await ac.post(
        "/api/v1/purchasing/grn",
        headers=io,
        json={
            "purchase_order_id": po_id,
            "items": [
                {"po_item_id": po_item_id, "received_qty": 5, "accepted_qty": 4},
            ],
        },
    )
    assert missing.status_code == 400

    ok = await ac.post(
        "/api/v1/purchasing/grn",
        headers=io,
        json={
            "purchase_order_id": po_id,
            "items": [
                {
                    "po_item_id": po_item_id,
                    "received_qty": 5,
                    "accepted_qty": 4,
                    "rejection_reason": "Wrong item",
                }
            ],
        },
    )
    assert ok.status_code == 200, ok.text
    item = ok.json()["data"]["items"][0]
    assert item["rejected_qty"] == 1.0
    assert item["rejection_reason"] == "Wrong item"
