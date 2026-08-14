"""Purchase return reason required (BR-6.6)."""

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
        full_name="IO Return Reason",
        password_hash=hash_password("SecurePass123!"),
        role="inventory_officer",
        email_verified=True,
        permissions=permissions_for_role("inventory_officer"),
        totp_enabled=False,
    )
    db_session.add(user)
    await db_session.commit()
    return user


async def _posted_grn(ac, db_session, *, admin, io, seed, vendor: str):
    product = await db_session.get(m.Product, seed["p1"].id)
    product.tracks_batches = False
    await db_session.commit()

    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=admin,
        json={"name": vendor, "kind": "supplier", "email": f"{vendor.replace(' ', '').lower()}@example.com"},
    )
    assert supplier.status_code == 200, supplier.text
    created = await ac.post(
        "/api/v1/purchasing/orders",
        headers=io,
        json={
            "supplier_id": supplier.json()["data"]["id"],
            "items": [{"product_id": seed["p1"].id, "quantity": 4, "unit_price": 5, "tax_rate": 0}],
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
                    "received_qty": 4,
                    "accepted_qty": 4,
                    "rejected_qty": 0,
                }
            ],
        },
    )
    assert grn.status_code == 200, grn.text
    body = grn.json()["data"]
    return body["id"], body["items"][0]["id"]


@pytest.mark.asyncio
async def test_purchase_return_reason_required(client, db_session):
    ac, seed = client
    await _seed_io(db_session, seed, email="io-ret-req@alpha.example.com")
    admin = await _super(ac, seed)
    io = await auth_headers(ac, email="io-ret-req@alpha.example.com", tenant_slug="alpha")
    grn_id, grn_item_id = await _posted_grn(
        ac, db_session, admin=admin, io=io, seed=seed, vendor="Return Reason Req"
    )

    missing = await ac.post(
        "/api/v1/purchasing/returns",
        headers=io,
        json={
            "goods_receipt_id": grn_id,
            "items": [{"goods_receipt_item_id": grn_item_id, "quantity": 1}],
        },
    )
    assert missing.status_code == 422, missing.text

    blank = await ac.post(
        "/api/v1/purchasing/returns",
        headers=io,
        json={
            "goods_receipt_id": grn_id,
            "reason": "   ",
            "items": [{"goods_receipt_item_id": grn_item_id, "quantity": 1}],
        },
    )
    assert blank.status_code == 400, blank.text
    assert "reason" in blank.text.lower()


@pytest.mark.asyncio
async def test_purchase_return_explicit_reasons(client, db_session):
    ac, seed = client
    await _seed_io(db_session, seed, email="io-ret-ok@alpha.example.com")
    admin = await _super(ac, seed)
    io = await auth_headers(ac, email="io-ret-ok@alpha.example.com", tenant_slug="alpha")
    grn_id, grn_item_id = await _posted_grn(
        ac, db_session, admin=admin, io=io, seed=seed, vendor="Return Reason OK"
    )

    for reason in ("damaged", "wrong_item", "expiry", "quality", "other"):
        created = await ac.post(
            "/api/v1/purchasing/returns",
            headers=io,
            json={
                "goods_receipt_id": grn_id,
                "reason": reason,
                "items": [{"goods_receipt_item_id": grn_item_id, "quantity": 0.5}],
            },
        )
        assert created.status_code == 200, f"{reason}: {created.text}"
        assert created.json()["data"]["reason"] == reason


@pytest.mark.asyncio
async def test_purchase_return_invalid_reason_rejected(client, db_session):
    ac, seed = client
    await _seed_io(db_session, seed, email="io-ret-bad@alpha.example.com")
    admin = await _super(ac, seed)
    io = await auth_headers(ac, email="io-ret-bad@alpha.example.com", tenant_slug="alpha")
    grn_id, grn_item_id = await _posted_grn(
        ac, db_session, admin=admin, io=io, seed=seed, vendor="Return Reason Bad"
    )

    bad = await ac.post(
        "/api/v1/purchasing/returns",
        headers=io,
        json={
            "goods_receipt_id": grn_id,
            "reason": "not_a_reason",
            "items": [{"goods_receipt_item_id": grn_item_id, "quantity": 1}],
        },
    )
    assert bad.status_code == 400, bad.text
    assert "reason" in bad.text.lower()
