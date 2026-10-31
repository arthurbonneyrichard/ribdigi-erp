"""Restaurant staff roles: each does one job, enforced on the server."""

from __future__ import annotations

import pytest

from tests.conftest import auth_headers, set_tenant_industry

pytestmark = pytest.mark.asyncio


async def _staff(ac, admin, role: str) -> dict:
    email = f"{role}@alpha.example.com"
    made = await ac.post(
        "/api/v1/users",
        headers=admin,
        json={"email": email, "full_name": role.replace("_", " ").title(), "password": "SecurePass123!", "role": role},
    )
    assert made.status_code == 200, made.text
    return await auth_headers(ac, email=email, tenant_slug="alpha")


async def test_restaurant_roles_only_for_restaurants(client, db_session):
    ac, seed = client
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    refused = await ac.post(
        "/api/v1/users",
        headers=admin,
        json={"email": "w@alpha.example.com", "full_name": "Waiter", "password": "SecurePass123!", "role": "restaurant_waiter"},
    )
    assert refused.status_code in {400, 422}, refused.text


async def test_waiter_cashier_kitchen_jobs(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    dish = await ac.post("/api/v1/products", headers=admin, json={"name": "Role jollof", "selling_price": 30, "stock_qty": 50, "prep_station": "kitchen"})
    dish_id = dish.json()["data"]["id"]
    body = {"service_mode": "takeaway", "payment_method": "cash", "customer_name": "Ama", "lines": [{"product_id": dish_id, "quantity": "1"}]}

    waiter = await _staff(ac, admin, "restaurant_waiter")
    order = await ac.post("/api/v1/restaurant/orders", headers=waiter, json=body)
    assert order.status_code == 200, order.text
    oid = order.json()["data"]["id"]
    assert (await ac.post(f"/api/v1/restaurant/orders/{oid}/send", headers=waiter)).status_code == 200
    pay = await ac.post(f"/api/v1/restaurant/orders/{oid}/complete", headers=waiter)
    assert pay.status_code == 403 and pay.json()["detail"]["code"] == "RESTAURANT_ROLE_JOB", pay.text
    assert (await ac.post("/api/v1/restaurant/till/shift/open", headers=waiter, json={"opening_cash": 10})).status_code == 403
    assert (await ac.get("/api/v1/restaurant/orders", headers=waiter)).status_code == 200

    kitchen = await _staff(ac, admin, "restaurant_kitchen")
    assert (await ac.post("/api/v1/restaurant/orders", headers=kitchen, json=body)).status_code == 403
    assert (await ac.put("/api/v1/restaurant/sold-out", headers=kitchen, json={"product_ids": []})).status_code == 200

    cashier = await _staff(ac, admin, "restaurant_cashier")
    opened = await ac.post("/api/v1/restaurant/till/shift/open", headers=cashier, json={"opening_cash": 10})
    assert opened.status_code == 200, opened.text
    paid = await ac.post(f"/api/v1/restaurant/orders/{oid}/complete", headers=cashier)
    assert paid.status_code == 200, paid.text
    refund = await ac.post(f"/api/v1/restaurant/orders/{oid}/refund", headers=cashier)
    assert refund.status_code == 403, refund.text
    assert (await ac.post("/api/v1/restaurant/tables", headers=cashier, json={"code": "T9", "name": "Patio 9", "seats": 2})).status_code == 403

    manager = await _staff(ac, admin, "restaurant_manager")
    table = await ac.post("/api/v1/restaurant/tables", headers=manager, json={"code": "T9", "name": "Patio 9", "seats": 2})
    assert table.status_code == 200, table.text


def test_restaurant_role_menus_and_homes():
    from pathlib import Path

    root = Path(__file__).resolve().parents[2] / "frontend"
    nav = (root / "lib/tenantNav.ts").read_text(encoding="utf-8")
    shell = (root / "components/Shell.tsx").read_text(encoding="utf-8")
    assert "export const RESTAURANT_ROLE_HREFS" in nav
    assert "if (role === 'restaurant_kitchen') return '/restaurant?tab=kitchen';" in nav
    assert "if (role === 'restaurant_waiter' || role === 'restaurant_cashier') return '/restaurant/till';" in nav
    assert "navItemVisibleForRole(role, href, true)" in shell
    for role in ("restaurant_manager", "restaurant_cashier", "restaurant_waiter", "restaurant_kitchen"):
        assert f"  {role}: [" in shell
