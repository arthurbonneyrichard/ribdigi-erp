"""Hotel + FMCG completion R3 — settings, groups, reports, schemes, dispatch."""

from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

import pyotp
import pytest

from tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_hotel_settings_group_reports_confirmation(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:6]

    settings = await ac.patch(
        "/api/v1/hotel/settings",
        headers=admin,
        json={
            "check_in_time": "15:00",
            "check_out_time": "10:00",
            "cancellation_hours": 48,
            "tax_percent": 5,
        },
    )
    assert settings.status_code == 200, settings.text
    assert settings.json()["data"]["check_in_time"] == "15:00"
    assert settings.json()["data"]["cancellation_hours"] == 48

    g = await ac.post(
        "/api/v1/hotel/guests",
        headers=admin,
        json={"full_name": f"Group Guest {suffix}"},
    )
    assert g.status_code == 200
    r1 = await ac.post(
        "/api/v1/hotel/rooms",
        headers=admin,
        json={"code": f"G1{suffix}", "name": "G1", "rate_amount": 100, "weekend_rate": 140},
    )
    r2 = await ac.post(
        "/api/v1/hotel/rooms",
        headers=admin,
        json={"code": f"G2{suffix}", "name": "G2", "rate_amount": 110},
    )
    assert r1.status_code == 200 and r2.status_code == 200
    check_in = date.today() + timedelta(days=2)
    check_out = check_in + timedelta(days=2)
    group = await ac.post(
        "/api/v1/hotel/reservation-groups",
        headers=admin,
        json={
            "guest_id": g.json()["data"]["id"],
            "room_ids": [r1.json()["data"]["id"], r2.json()["data"]["id"]],
            "check_in_date": check_in.isoformat(),
            "check_out_date": check_out.isoformat(),
            "booking_source": "corporate",
            "name": f"Corp {suffix}",
        },
    )
    assert group.status_code == 200, group.text
    assert len(group.json()["data"]["reservations"]) == 2
    res_id = group.json()["data"]["reservations"][0]["id"]

    conf = await ac.get(
        f"/api/v1/hotel/reservations/{res_id}/confirmation",
        headers=admin,
    )
    assert conf.status_code == 200, conf.text
    assert "RESERVATION CONFIRMATION" in conf.json()["data"]["text"]
    assert "15:00" in conf.json()["data"]["text"]

    cal = await ac.get(
        f"/api/v1/hotel/calendar?start_date={check_in.isoformat()}&end_date={check_out.isoformat()}",
        headers=admin,
    )
    assert cal.status_code == 200, cal.text
    assert cal.json()["data"]["rooms"]

    reports = await ac.get(
        f"/api/v1/hotel/reports?start_date={check_in.isoformat()}&end_date={check_out.isoformat()}",
        headers=admin,
    )
    assert reports.status_code == 200, reports.text
    assert "adr" in reports.json()["data"]
    assert "revpar" in reports.json()["data"]


@pytest.mark.asyncio
async def test_fmcg_scheme_applies_on_sales_order_and_dispatch(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:6]

    # Ensure product exists via catalog create if available
    product = await ac.post(
        "/api/v1/products",
        headers=admin,
        json={
            "name": f"FMCG Item {suffix}",
            "sku": f"SKU{suffix}",
            "selling_price": 100,
            "cost_price": 50,
        },
    )
    assert product.status_code == 200, product.text
    product_id = product.json()["data"]["id"]

    scheme = await ac.post(
        "/api/v1/fmcg/schemes",
        headers=admin,
        json={
            "code": f"AP{suffix}",
            "name": "10pct",
            "scheme_type": "percent",
            "value": 10,
            "product_id": product_id,
        },
    )
    assert scheme.status_code == 200, scheme.text

    customer = await ac.post(
        "/api/v1/customers",
        headers=admin,
        json={"name": f"Scheme Cust {suffix}", "profile_type": "registered"},
    )
    assert customer.status_code == 200, customer.text
    customer_id = customer.json()["data"]["id"]

    order = await ac.post(
        "/api/v1/sales/orders",
        headers=admin,
        json={
            "customer_id": customer_id,
            "items": [{"product_id": product_id, "quantity": 2}],
        },
    )
    assert order.status_code == 200, order.text
    items = order.json()["data"].get("items") or []
    # discount should be applied (~20 on 200)
    if items:
        assert float(items[0].get("discount") or 0) >= 19.0

    route = await ac.post(
        "/api/v1/fmcg/routes",
        headers=admin,
        json={"code": f"D{suffix}", "name": f"Dispatch Route {suffix}"},
    )
    assert route.status_code == 200
    route_id = route.json()["data"]["id"]

    assign = await ac.post(
        "/api/v1/fmcg/assignments",
        headers=admin,
        json={
            "customer_id": customer_id,
            "route_id": route_id,
            "salesperson_name": "Rep One",
        },
    )
    assert assign.status_code == 200, assign.text

    dispatch = await ac.post(
        "/api/v1/fmcg/dispatches",
        headers=admin,
        json={"route_id": route_id},
    )
    assert dispatch.status_code == 200, dispatch.text
    closed = await ac.post(
        f"/api/v1/fmcg/dispatches/{dispatch.json()['data']['id']}/close",
        headers=admin,
        json={},
    )
    assert closed.status_code == 200, closed.text
    assert closed.json()["data"]["status"] == "closed"
