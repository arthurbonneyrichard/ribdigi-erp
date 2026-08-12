"""Customer groups + group-based list pricing (BR-7.1)."""

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
async def test_customer_group_defaults_and_pricing(client, db_session):
    ac, seed = client
    admin = await _admin(ac, seed)

    groups = await ac.get("/api/v1/customers/groups", headers=admin)
    assert groups.status_code == 200, groups.text
    by_code = {g["code"]: g for g in groups.json()["data"]}
    assert "RETAIL" in by_code
    assert "WHOLESALE" in by_code
    assert float(by_code["WHOLESALE"]["discount_percent"]) == 10.0
    assert float(by_code["VIP"]["discount_percent"]) == 15.0

    vip = by_code["VIP"]
    cust = await ac.post(
        "/api/v1/customers",
        headers=admin,
        json={
            "name": "VIP Buyer",
            "email": "vip@alpha.example.com",
            "customer_group_id": vip["id"],
        },
    )
    assert cust.status_code == 200, cust.text
    customer_id = cust.json()["data"]["id"]
    assert cust.json()["data"]["customer_group"]["code"] == "VIP"

    listed = await ac.get("/api/v1/customers", headers=admin)
    assert listed.status_code == 200
    match = next(c for c in listed.json()["data"] if c["id"] == customer_id)
    assert match["customer_group"]["discount_percent"] == 15.0

    price = await ac.get(
        f"/api/v1/products/{seed['p1'].id}/price",
        headers=admin,
        params={"customer_id": customer_id},
    )
    assert price.status_code == 200, price.text
    body = price.json()["data"]
    list_price = float(seed["p1"].selling_price)
    assert body["list_price"] == list_price
    assert body["unit_price"] == round(list_price * 0.85, 2)
    assert body["discount_percent"] == 15.0

    # Omit unit_price → group discount applied on invoice
    inv = await ac.post(
        "/api/v1/sales/invoices",
        headers=admin,
        json={
            "customer_id": customer_id,
            "items": [{"product_id": seed["p1"].id, "quantity": 2}],
        },
    )
    assert inv.status_code == 200, inv.text
    inv_data = inv.json()["data"]
    expected_unit = round(list_price * 0.85, 2)
    assert float(inv_data["items"][0]["unit_price"]) == expected_unit

    # Explicit unit_price overrides group discount
    override = await ac.post(
        "/api/v1/sales/invoices",
        headers=admin,
        json={
            "customer_id": customer_id,
            "items": [
                {
                    "product_id": seed["p1"].id,
                    "quantity": 1,
                    "unit_price": 9.99,
                }
            ],
        },
    )
    assert override.status_code == 200, override.text
    assert float(override.json()["data"]["items"][0]["unit_price"]) == 9.99


@pytest.mark.asyncio
async def test_customer_group_tenant_isolation(client, db_session):
    ac, seed = client
    admin = await _admin(ac, seed)
    groups = await ac.get("/api/v1/customers/groups", headers=admin)
    vip_id = next(g["id"] for g in groups.json()["data"] if g["code"] == "VIP")

    from app import models as m
    from app.rbac import permissions_for_role
    from app.security import hash_password
    from sqlalchemy import select

    beta_tenant = (
        await db_session.execute(select(m.Tenant).where(m.Tenant.slug == "beta"))
    ).scalar_one()
    beta_mgr = m.User(
        tenant_id=beta_tenant.id,
        email="mgr@beta.example.com",
        full_name="Beta Manager",
        password_hash=hash_password("SecurePass123!"),
        role="store_manager",
        email_verified=True,
        permissions=permissions_for_role("store_manager"),
        totp_enabled=False,
    )
    db_session.add(beta_mgr)
    await db_session.commit()

    beta_headers = await auth_headers(ac, email="mgr@beta.example.com", tenant_slug="beta")
    steal = await ac.post(
        "/api/v1/customers",
        headers=beta_headers,
        json={"name": "Steal", "customer_group_id": vip_id},
    )
    assert steal.status_code == 404, steal.text

    patch = await ac.patch(
        f"/api/v1/customers/groups/{vip_id}",
        headers=beta_headers,
        json={"discount_percent": 99},
    )
    assert patch.status_code == 404, patch.text


@pytest.mark.asyncio
async def test_create_custom_group_and_assign(client, db_session):
    ac, seed = client
    admin = await _admin(ac, seed)
    created = await ac.post(
        "/api/v1/customers/groups",
        headers=admin,
        json={"name": "Partners", "discount_percent": 20},
    )
    assert created.status_code == 200, created.text
    assert created.json()["data"]["code"] == "PARTNERS"
    assert float(created.json()["data"]["discount_percent"]) == 20.0
    gid = created.json()["data"]["id"]

    cust = await ac.post(
        "/api/v1/customers",
        headers=admin,
        json={"name": "Partner Co"},
    )
    cid = cust.json()["data"]["id"]
    patched = await ac.patch(
        f"/api/v1/customers/{cid}",
        headers=admin,
        json={"customer_group_id": gid},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["data"]["customer_group"]["name"] == "Partners"

    price = await ac.get(
        f"/api/v1/products/{seed['p1'].id}/price",
        headers=admin,
        params={"customer_id": cid},
    )
    assert price.json()["data"]["unit_price"] == round(
        float(seed["p1"].selling_price) * 0.8, 2
    )
