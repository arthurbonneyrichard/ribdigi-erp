"""BR-7.1 customer groups, GPS coordinates, and group-based pricing."""

from __future__ import annotations

import pytest

from tests.conftest import auth_headers


async def _sales(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


@pytest.mark.asyncio
async def test_customer_groups_crud_defaults_and_assign(client):
    ac, seed = client
    headers = await _sales(ac)

    listed = await ac.get("/api/v1/customers/groups", headers=headers)
    assert listed.status_code == 200, listed.text
    groups = listed.json()["data"]
    names = {g["name"] for g in groups}
    assert {"Retail", "Wholesale", "VIP"}.issubset(names)
    wholesale = next(g for g in groups if g["name"] == "Wholesale")
    assert float(wholesale["discount_percent"]) == 10

    created = await ac.post(
        "/api/v1/customers/groups",
        headers=headers,
        json={"name": "Staff", "discount_percent": 5},
    )
    assert created.status_code == 200, created.text
    staff = created.json()["data"]
    assert staff["name"] == "Staff"
    assert float(staff["discount_percent"]) == 5

    dup = await ac.post(
        "/api/v1/customers/groups",
        headers=headers,
        json={"name": "staff", "discount_percent": 1},
    )
    assert dup.status_code == 409

    patched = await ac.patch(
        f"/api/v1/customers/groups/{staff['id']}",
        headers=headers,
        json={"discount_percent": 7.5},
    )
    assert patched.status_code == 200, patched.text
    assert float(patched.json()["data"]["discount_percent"]) == 7.5

    customer = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={
            "name": "Wholesale Buyer",
            "code": "WS-1",
            "customer_group": "Wholesale",
            "latitude": 5.6037,
            "longitude": -0.187,
            "credit_limit": 1000,
        },
    )
    assert customer.status_code == 200, customer.text
    body = customer.json()["data"]
    assert body["customer_group_name"] == "Wholesale"
    assert float(body["group_discount_percent"]) == 10
    assert abs(float(body["latitude"]) - 5.6037) < 1e-6
    assert abs(float(body["longitude"]) + 0.187) < 1e-6

    by_id = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={
            "name": "VIP Buyer",
            "customer_group_id": next(g["id"] for g in groups if g["name"] == "VIP"),
        },
    )
    assert by_id.status_code == 200, by_id.text
    assert by_id.json()["data"]["customer_group_name"] == "VIP"
    assert float(by_id.json()["data"]["group_discount_percent"]) == 15

    cleared = await ac.patch(
        f"/api/v1/customers/{body['id']}",
        headers=headers,
        json={"customer_group_id": None, "latitude": None, "longitude": None},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["data"]["customer_group_id"] is None
    assert cleared.json()["data"]["latitude"] is None
    assert cleared.json()["data"]["longitude"] is None

    deactivated = await ac.delete(f"/api/v1/customers/groups/{staff['id']}", headers=headers)
    assert deactivated.status_code == 200, deactivated.text
    assert deactivated.json()["data"]["is_active"] is False


@pytest.mark.asyncio
async def test_gps_validation_and_group_pricing_on_invoice(client):
    ac, seed = client
    headers = await _sales(ac)

    bad_gps = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": "Half GPS", "latitude": 1.0},
    )
    assert bad_gps.status_code == 400

    out_of_range = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": "Bad Lat", "latitude": 91, "longitude": 0},
    )
    assert out_of_range.status_code == 400

    groups = (await ac.get("/api/v1/customers/groups", headers=headers)).json()["data"]
    vip_id = next(g["id"] for g in groups if g["name"] == "VIP")

    customer = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={
            "name": "Priced VIP",
            "customer_group_id": vip_id,
            "credit_limit": 5000,
        },
    )
    assert customer.status_code == 200, customer.text
    customer_id = customer.json()["data"]["id"]

    catalog_price = float(seed["p1"].selling_price)
    expected = round(catalog_price * 0.85, 4)

    inv = await ac.post(
        "/api/v1/sales/invoices",
        headers=headers,
        json={
            "customer_id": customer_id,
            "items": [{"product_id": seed["p1"].id, "quantity": 2}],
        },
    )
    assert inv.status_code == 200, inv.text
    item = inv.json()["data"]["items"][0]
    assert abs(float(item["unit_price"]) - expected) < 0.0001

    override = await ac.post(
        "/api/v1/sales/invoices",
        headers=headers,
        json={
            "customer_id": customer_id,
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 99.0}],
        },
    )
    assert override.status_code == 200, override.text
    assert float(override.json()["data"]["items"][0]["unit_price"]) == 99.0


@pytest.mark.asyncio
async def test_group_pricing_on_pos_sale(client):
    ac, seed = client
    headers = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    mgr = await _sales(ac)

    groups = (await ac.get("/api/v1/customers/groups", headers=mgr)).json()["data"]
    wholesale_id = next(g["id"] for g in groups if g["name"] == "Wholesale")
    customer = await ac.post(
        "/api/v1/customers",
        headers=mgr,
        json={
            "name": "POS Wholesale",
            "customer_group_id": wholesale_id,
            "credit_limit": 2000,
        },
    )
    customer_id = customer.json()["data"]["id"]

    opened = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=headers,
        json={"opening_cash": 50},
    )
    assert opened.status_code == 200, opened.text
    session_id = opened.json()["data"]["session_id"]

    catalog_price = float(seed["p1"].selling_price)
    expected_unit = round(catalog_price * 0.9, 4)

    sale = await ac.post(
        "/api/v1/pos/sales",
        headers=headers,
        json={
            "session_id": session_id,
            "party_id": customer_id,
            "payment_method": "cash",
            "items": [{"product_id": seed["p1"].id, "quantity": 1}],
        },
    )
    assert sale.status_code == 200, sale.text
    assert abs(float(sale.json()["data"]["subtotal"]) - expected_unit) < 0.02

    receipt = await ac.get(
        f"/api/v1/pos/sales/{sale.json()['data']['id']}/receipt", headers=headers
    )
    assert receipt.status_code == 200, receipt.text
    lines = receipt.json()["data"].get("items") or []
    assert lines
    assert abs(float(lines[0]["unit_price"]) - expected_unit) < 0.0001
