"""Purchase return credit inherits proportional PO line discount (BR-6.6)."""

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


async def _seed_io(db_session, seed, email: str):
    user = m.User(
        tenant_id=seed["t1"].id,
        email=email,
        full_name="IO Return Disc",
        password_hash=hash_password("SecurePass123!"),
        role="inventory_officer",
        email_verified=True,
        permissions=permissions_for_role("inventory_officer"),
        totp_enabled=False,
    )
    db_session.add(user)
    await db_session.commit()
    return user


async def _discounted_grn(ac, db_session, *, admin, io, seed, vendor: str, qty=4.0, disc=8.0):
    product = await db_session.get(m.Product, seed["p1"].id)
    product.tracks_batches = False
    await db_session.commit()

    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=admin,
        json={
            "name": vendor,
            "kind": "supplier",
            "email": f"{vendor.replace(' ', '').lower()}@example.com",
        },
    )
    assert supplier.status_code == 200, supplier.text
    created = await ac.post(
        "/api/v1/purchasing/orders",
        headers=io,
        json={
            "supplier_id": supplier.json()["data"]["id"],
            "items": [
                {
                    "product_id": seed["p1"].id,
                    "quantity": qty,
                    "unit_price": 10,
                    "tax_rate": 10,
                    "discount": disc,
                }
            ],
        },
    )
    assert created.status_code == 200, created.text
    po = created.json()["data"]
    po_row = await db_session.get(m.PurchaseOrder, po["id"])
    po_row.status = "sent"
    await db_session.commit()

    grn = await ac.post(
        "/api/v1/purchasing/grn",
        headers=io,
        json={
            "purchase_order_id": po["id"],
            "items": [
                {
                    "po_item_id": po["items"][0]["id"],
                    "received_qty": qty,
                    "accepted_qty": qty,
                    "rejected_qty": 0,
                }
            ],
        },
    )
    assert grn.status_code == 200, grn.text
    body = grn.json()["data"]
    return body["id"], body["items"][0]["id"], po


@pytest.mark.asyncio
async def test_return_inherits_full_po_line_discount(client, db_session):
    ac, seed = client
    await _seed_io(db_session, seed, email="io-ret-disc-full@alpha.example.com")
    admin = await _super(ac, seed)
    io = await auth_headers(ac, email="io-ret-disc-full@alpha.example.com", tenant_slug="alpha")
    grn_id, grn_item_id, po = await _discounted_grn(
        ac, db_session, admin=admin, io=io, seed=seed, vendor="Return Disc Full"
    )
    assert po["total_amount"] == 36  # 40+4-8

    created = await ac.post(
        "/api/v1/purchasing/returns",
        headers=io,
        json={
            "goods_receipt_id": grn_id,
            "reason": "damaged",
            "items": [{"goods_receipt_item_id": grn_item_id, "quantity": 4}],
        },
    )
    assert created.status_code == 200, created.text
    body = created.json()["data"]
    assert body["items"][0]["discount"] == 8
    assert body["discount_amount"] == 8
    assert body["subtotal"] == 40
    assert body["tax_amount"] == 4
    assert body["total_amount"] == 36
    assert body["items"][0]["line_total"] == 36

    posted = await ac.post(
        f"/api/v1/purchasing/returns/{body['id']}/post",
        headers=admin,
        json={},
    )
    assert posted.status_code == 200, posted.text
    assert posted.json()["data"]["total_amount"] == 36
    assert posted.json()["data"]["discount_amount"] == 8


@pytest.mark.asyncio
async def test_return_partial_qty_proportional_discount(client, db_session):
    ac, seed = client
    await _seed_io(db_session, seed, email="io-ret-disc-part@alpha.example.com")
    admin = await _super(ac, seed)
    io = await auth_headers(ac, email="io-ret-disc-part@alpha.example.com", tenant_slug="alpha")
    grn_id, grn_item_id, _po = await _discounted_grn(
        ac, db_session, admin=admin, io=io, seed=seed, vendor="Return Disc Part", qty=4, disc=8
    )

    created = await ac.post(
        "/api/v1/purchasing/returns",
        headers=io,
        json={
            "goods_receipt_id": grn_id,
            "reason": "quality",
            "items": [{"goods_receipt_item_id": grn_item_id, "quantity": 2}],
        },
    )
    assert created.status_code == 200, created.text
    body = created.json()["data"]
    assert body["items"][0]["discount"] == 4  # half of 8
    assert body["discount_amount"] == 4
    assert body["subtotal"] == 20
    assert body["tax_amount"] == 2
    assert body["total_amount"] == 18  # 22 - 4


@pytest.mark.asyncio
async def test_return_zero_po_discount_unchanged(client, db_session):
    ac, seed = client
    await _seed_io(db_session, seed, email="io-ret-disc-zero@alpha.example.com")
    admin = await _super(ac, seed)
    io = await auth_headers(ac, email="io-ret-disc-zero@alpha.example.com", tenant_slug="alpha")
    grn_id, grn_item_id, _po = await _discounted_grn(
        ac, db_session, admin=admin, io=io, seed=seed, vendor="Return Disc Zero", qty=2, disc=0
    )

    created = await ac.post(
        "/api/v1/purchasing/returns",
        headers=io,
        json={
            "goods_receipt_id": grn_id,
            "reason": "other",
            "items": [{"goods_receipt_item_id": grn_item_id, "quantity": 1}],
        },
    )
    assert created.status_code == 200, created.text
    body = created.json()["data"]
    assert body["items"][0]["discount"] == 0
    assert body["discount_amount"] == 0
    assert body["total_amount"] == 11  # 10 + 1 tax
