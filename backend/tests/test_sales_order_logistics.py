"""BR-7.3 order logistics statuses and delivery fields."""

from __future__ import annotations

from datetime import datetime

import pytest

from app.inventory import apply_stock_change
from tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_order_delivery_fields_and_status_flow(client, db_session):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    product_id = seed["p1"].id
    customer_id = seed["party1"].id

    await apply_stock_change(
        db_session,
        tenant_id=seed["t1"].id,
        product_id=product_id,
        quantity_delta=5,
        movement_type="stock_in",
        user_id=seed["mgr1"].id,
    )
    await db_session.commit()

    created = await ac.post(
        "/api/v1/sales/orders",
        headers=headers,
        json={
            "customer_id": customer_id,
            "delivery_date": "2026-08-15T00:00:00",
            "delivery_address": "12 Market St",
            "items": [{"product_id": product_id, "quantity": 1, "unit_price": 9}],
        },
    )
    assert created.status_code == 200, created.text
    order = created.json()["data"]
    order_id = order["id"]
    assert order["delivery_address"] == "12 Market St"
    assert str(order["delivery_date"]).startswith("2026-08-15")

    patched = await ac.patch(
        f"/api/v1/sales/orders/{order_id}",
        headers=headers,
        json={"delivery_address": "99 Harbor Rd", "notes": "Leave at dock"},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["data"]["delivery_address"] == "99 Harbor Rd"
    assert patched.json()["data"]["notes"] == "Leave at dock"

    assert (await ac.post(f"/api/v1/sales/orders/{order_id}/confirm", headers=headers)).status_code == 200

    processing = await ac.post(f"/api/v1/sales/orders/{order_id}/process", headers=headers)
    assert processing.status_code == 200, processing.text
    assert processing.json()["data"]["status"] == "processing"
    assert processing.json()["data"]["processing_at"] is not None

    # Cannot skip to delivered from processing
    skip = await ac.post(f"/api/v1/sales/orders/{order_id}/deliver", headers=headers)
    assert skip.status_code == 409

    shipped = await ac.post(f"/api/v1/sales/orders/{order_id}/ship", headers=headers)
    assert shipped.status_code == 200, shipped.text
    assert shipped.json()["data"]["status"] == "shipped"

    delivered = await ac.post(f"/api/v1/sales/orders/{order_id}/deliver", headers=headers)
    assert delivered.status_code == 200, delivered.text
    data = delivered.json()["data"]
    assert data["status"] == "delivered"
    assert data["delivered_at"] is not None

    # Cancel not allowed after ship/deliver
    cancel = await ac.post(f"/api/v1/sales/orders/{order_id}/cancel", headers=headers)
    assert cancel.status_code == 409

    converted = await ac.post(f"/api/v1/sales/orders/{order_id}/convert-invoice", headers=headers)
    assert converted.status_code == 200, converted.text
    assert converted.json()["data"]["status"] == "draft"


@pytest.mark.asyncio
async def test_cancel_from_processing_releases_stock(client, db_session):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    product_id = seed["p1"].id
    customer_id = seed["party1"].id

    await apply_stock_change(
        db_session,
        tenant_id=seed["t1"].id,
        product_id=product_id,
        quantity_delta=4,
        movement_type="stock_in",
        user_id=seed["mgr1"].id,
    )
    await db_session.commit()

    created = await ac.post(
        "/api/v1/sales/orders",
        headers=headers,
        json={
            "customer_id": customer_id,
            "items": [{"product_id": product_id, "quantity": 2, "unit_price": 3}],
        },
    )
    order_id = created.json()["data"]["id"]
    assert (await ac.post(f"/api/v1/sales/orders/{order_id}/confirm", headers=headers)).status_code == 200
    assert (await ac.post(f"/api/v1/sales/orders/{order_id}/process", headers=headers)).status_code == 200

    cancelled = await ac.post(f"/api/v1/sales/orders/{order_id}/cancel", headers=headers)
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["data"]["status"] == "cancelled"
    assert cancelled.json()["data"]["reserved_qty_total"] == 0


@pytest.mark.asyncio
async def test_default_delivery_address_from_customer(client, db_session):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    seed["party1"].address = "Customer Default Ave"
    await db_session.commit()
    customer_id = seed["party1"].id
    product_id = seed["p1"].id

    created = await ac.post(
        "/api/v1/sales/orders",
        headers=headers,
        json={
            "customer_id": customer_id,
            "items": [{"product_id": product_id, "quantity": 1, "unit_price": 1}],
        },
    )
    assert created.status_code == 200, created.text
    assert created.json()["data"]["delivery_address"] == "Customer Default Ave"
    assert created.json()["data"]["delivery_date"] is None or isinstance(
        created.json()["data"]["delivery_date"], (str, type(None), datetime)
    )
