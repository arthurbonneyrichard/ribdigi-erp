"""From-GRN purchase invoice inherits PO line discount (BR-6.5)."""

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
        full_name="IO PI GRN Disc",
        password_hash=hash_password("SecurePass123!"),
        role="inventory_officer",
        email_verified=True,
        permissions=permissions_for_role("inventory_officer"),
        totp_enabled=False,
    )
    db_session.add(user)
    await db_session.commit()
    return user


async def _grn_from_discounted_po(ac, db_session, *, admin, io, seed, vendor: str):
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
                    "quantity": 4,
                    "unit_price": 10,
                    "tax_rate": 10,
                    "discount": 8,
                }
            ],
        },
    )
    assert created.status_code == 200, created.text
    po = created.json()["data"]
    assert po["items"][0]["discount"] == 8
    # total = 40 + 4 - 8 = 36
    assert po["total_amount"] == 36

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
                    "received_qty": 4,
                    "accepted_qty": 4,
                    "rejected_qty": 0,
                }
            ],
        },
    )
    assert grn.status_code == 200, grn.text
    return grn.json()["data"]["id"], po


@pytest.mark.asyncio
async def test_from_grn_pi_inherits_po_line_discount(client, db_session):
    ac, seed = client
    await _seed_io(db_session, seed, email="io-pi-grn-disc@alpha.example.com")
    admin = await _super(ac, seed)
    io = await auth_headers(ac, email="io-pi-grn-disc@alpha.example.com", tenant_slug="alpha")
    grn_id, po = await _grn_from_discounted_po(
        ac, db_session, admin=admin, io=io, seed=seed, vendor="PI GRN Disc Vendor"
    )

    inv = await ac.post(
        "/api/v1/purchasing/invoices",
        headers=admin,
        json={"goods_receipt_id": grn_id},
    )
    assert inv.status_code == 200, inv.text
    body = inv.json()["data"]
    assert body["items"][0]["discount"] == 8
    assert body["discount_amount"] == 8
    assert body["subtotal"] == 40
    assert body["tax_amount"] == 4
    # total = gross 44 - header disc 8 = 36 (matches PO)
    assert body["total_amount"] == 36
    assert body["items"][0]["line_total"] == 36


@pytest.mark.asyncio
async def test_from_grn_pi_partial_receive_proportional_discount(client, db_session):
    ac, seed = client
    await _seed_io(db_session, seed, email="io-pi-grn-part@alpha.example.com")
    admin = await _super(ac, seed)
    io = await auth_headers(ac, email="io-pi-grn-part@alpha.example.com", tenant_slug="alpha")

    product = await db_session.get(m.Product, seed["p1"].id)
    product.tracks_batches = False
    await db_session.commit()

    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=admin,
        json={"name": "PI Partial Disc", "kind": "supplier", "email": "pi-part-d@example.com"},
    )
    assert supplier.status_code == 200
    created = await ac.post(
        "/api/v1/purchasing/orders",
        headers=io,
        json={
            "supplier_id": supplier.json()["data"]["id"],
            "items": [
                {
                    "product_id": seed["p1"].id,
                    "quantity": 4,
                    "unit_price": 10,
                    "tax_rate": 0,
                    "discount": 8,
                }
            ],
        },
    )
    assert created.status_code == 200, created.text
    po = created.json()["data"]
    po_row = await db_session.get(m.PurchaseOrder, po["id"])
    po_row.status = "sent"
    await db_session.commit()

    # Receive half → discount share 4
    grn = await ac.post(
        "/api/v1/purchasing/grn",
        headers=io,
        json={
            "purchase_order_id": po["id"],
            "items": [
                {
                    "po_item_id": po["items"][0]["id"],
                    "received_qty": 2,
                    "accepted_qty": 2,
                    "rejected_qty": 0,
                }
            ],
        },
    )
    assert grn.status_code == 200, grn.text

    inv = await ac.post(
        "/api/v1/purchasing/invoices",
        headers=admin,
        json={"goods_receipt_id": grn.json()["data"]["id"]},
    )
    assert inv.status_code == 200, inv.text
    body = inv.json()["data"]
    assert body["items"][0]["discount"] == 4
    assert body["discount_amount"] == 4
    assert body["subtotal"] == 20
    assert body["total_amount"] == 16


@pytest.mark.asyncio
async def test_from_grn_pi_explicit_header_discount_kept(client, db_session):
    ac, seed = client
    await _seed_io(db_session, seed, email="io-pi-grn-hdr@alpha.example.com")
    admin = await _super(ac, seed)
    io = await auth_headers(ac, email="io-pi-grn-hdr@alpha.example.com", tenant_slug="alpha")
    grn_id, _po = await _grn_from_discounted_po(
        ac, db_session, admin=admin, io=io, seed=seed, vendor="PI GRN Hdr Vendor"
    )

    inv = await ac.post(
        "/api/v1/purchasing/invoices",
        headers=admin,
        json={"goods_receipt_id": grn_id, "discount_amount": 2},
    )
    assert inv.status_code == 200, inv.text
    body = inv.json()["data"]
    assert body["items"][0]["discount"] == 8  # still carried on lines
    assert body["discount_amount"] == 2  # client header wins
    assert body["total_amount"] == 42  # 44 - 2
