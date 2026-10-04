"""UoM conversion ratios (BR-5.1)."""

from __future__ import annotations

import pyotp
import pytest

from tests.conftest import auth_headers


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_uom_catalog_and_stock_in_conversion(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)

    units = await ac.get("/api/v1/catalog/units", headers=headers)
    assert units.status_code == 200, units.text
    by_code = {u["code"]: u for u in units.json()["data"]}
    assert "PCS" in by_code
    pcs_id = by_code["PCS"]["id"]

    box = await ac.post(
        "/api/v1/catalog/units",
        headers=headers,
        json={
            "code": "CASE12",
            "name": "Case of 12",
            "base_unit_id": pcs_id,
            "conversion_ratio": 12,
        },
    )
    assert box.status_code == 200, box.text
    assert box.json()["data"]["conversion_ratio"] == 12.0
    assert box.json()["data"]["base_unit_code"] == "PCS"
    box_id = box.json()["data"]["id"]

    # Reject self-base / bad ratio
    bad = await ac.post(
        "/api/v1/catalog/units",
        headers=headers,
        json={"code": "BAD", "name": "Bad", "base_unit_id": pcs_id, "conversion_ratio": 0},
    )
    assert bad.status_code == 422

    # Product with stock unit PCS
    prod = await ac.post(
        "/api/v1/products",
        headers=headers,
        json={
            "name": "Widget Pack",
            "sku": "W-PACK-1",
            "cost_price": 1,
            "selling_price": 2,
            "stock_qty": 0,
            "unit_id": pcs_id,
        },
    )
    assert prod.status_code == 200, prod.text
    pid = prod.json()["data"]["id"]

    preview = await ac.post(
        "/api/v1/catalog/units/convert",
        headers=headers,
        json={"product_id": pid, "quantity": 2, "from_unit_id": box_id},
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["data"]["quantity_base"] == 24.0

    stock = await ac.post(
        "/api/v1/inventory/stock-in",
        headers=headers,
        json={"product_id": pid, "quantity": 2, "unit_id": box_id},
    )
    assert stock.status_code == 200, stock.text
    assert stock.json()["data"]["quantity_entered"] == 2.0
    assert stock.json()["data"]["quantity_base"] == 24.0
    assert stock.json()["data"]["stock_qty"] == 24.0

    # Default path unbroken (no unit_id)
    stock2 = await ac.post(
        "/api/v1/inventory/stock-in",
        headers=headers,
        json={"product_id": pid, "quantity": 3},
    )
    assert stock2.status_code == 200, stock2.text
    assert stock2.json()["data"]["stock_qty"] == 27.0

    # Incommensurable: BOX vs KG
    kg_id = by_code["KG"]["id"]
    fail = await ac.post(
        "/api/v1/inventory/stock-in",
        headers=headers,
        json={"product_id": pid, "quantity": 1, "unit_id": kg_id},
    )
    assert fail.status_code == 400


@pytest.mark.asyncio
async def test_uom_base_tenant_isolation(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    units = await ac.get("/api/v1/catalog/units", headers=headers)
    pcs_id = next(u["id"] for u in units.json()["data"] if u["code"] == "PCS")

    from app import models as m
    from app.rbac import permissions_for_role
    from app.security import hash_password
    from sqlalchemy import select

    beta = (
        await db_session.execute(select(m.Tenant).where(m.Tenant.slug == "beta"))
    ).scalar_one()
    mgr = m.User(
        tenant_id=beta.id,
        email="inv@beta.example.com",
        full_name="Beta Inv",
        password_hash=hash_password("SecurePass123!"),
        role="inventory_officer",
        email_verified=True,
        permissions=permissions_for_role("inventory_officer"),
        totp_enabled=False,
    )
    db_session.add(mgr)
    await db_session.commit()

    beta_h = await auth_headers(ac, email="inv@beta.example.com", tenant_slug="beta")
    steal = await ac.post(
        "/api/v1/catalog/units",
        headers=beta_h,
        json={
            "code": "STEAL",
            "name": "Steal",
            "base_unit_id": pcs_id,
            "conversion_ratio": 6,
        },
    )
    assert steal.status_code == 404, steal.text
