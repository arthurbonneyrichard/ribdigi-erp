"""Low-stock suggestions → draft purchase requests."""

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
        email="io-suggest@alpha.example.com",
        full_name="IO Suggest",
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
async def test_low_stock_suggestions_and_create_draft_pr(client, db_session):
    ac, seed = client
    await _seed_io(db_session, seed)
    admin = await _super(ac, seed)
    io = await auth_headers(ac, email="io-suggest@alpha.example.com", tenant_slug="alpha")

    # Put product below reorder
    product = seed["p1"]
    product.stock_qty = 2
    product.reorder_level = 10
    await db_session.commit()

    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=admin,
        json={"name": "Suggest Supplier", "kind": "supplier", "email": "s@example.com"},
    )
    assert supplier.status_code == 200, supplier.text
    supplier_id = supplier.json()["data"]["id"]

    # Seed a prior PO so preferred supplier resolves
    po = await ac.post(
        "/api/v1/purchasing/orders",
        headers=io,
        json={
            "supplier_id": supplier_id,
            "items": [{"product_id": product.id, "quantity": 1, "unit_price": 1}],
        },
    )
    assert po.status_code == 200, po.text

    listed = await ac.get("/api/v1/purchasing/suggestions/low-stock", headers=io)
    assert listed.status_code == 200, listed.text
    body = listed.json()["data"]
    assert body["count"] >= 1
    line = next(ln for ln in body["lines"] if ln["product_id"] == product.id)
    assert line["suggested_order_qty"] >= 8
    assert line["preferred_supplier_id"] == supplier_id

    created = await ac.post(
        "/api/v1/purchasing/requests/from-low-stock",
        headers=io,
        json={
            "lines": [
                {
                    "product_id": product.id,
                    "quantity": line["suggested_order_qty"],
                    "preferred_supplier_id": supplier_id,
                }
            ],
            "notes": "Auto from low stock",
        },
    )
    assert created.status_code == 200, created.text
    data = created.json()["data"]
    assert data["created_count"] == 1
    pr = data["created"][0]
    assert pr["status"] == "draft"
    assert pr["preferred_supplier_id"] == supplier_id
    assert any(i["product_id"] == product.id for i in pr["items"])

    # Dedupe: already on open PR
    again = await ac.post(
        "/api/v1/purchasing/requests/from-low-stock",
        headers=io,
        json={"lines": [{"product_id": product.id, "quantity": 5}]},
    )
    assert again.status_code == 400


@pytest.mark.asyncio
async def test_low_stock_suggestions_empty_lines_400(client, db_session):
    ac, seed = client
    await _seed_io(db_session, seed)
    io = await auth_headers(ac, email="io-suggest@alpha.example.com", tenant_slug="alpha")
    r = await ac.post(
        "/api/v1/purchasing/requests/from-low-stock",
        headers=io,
        json={"lines": []},
    )
    assert r.status_code == 422
