"""BR-7.3 soft allocation: reserve on confirm, release on cancel, consume on invoice post."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app import models as m
from app.inventory import apply_stock_change
from tests.conftest import auth_headers


async def _product(db, product_id: str) -> m.Product:
    return (
        await db.execute(select(m.Product).where(m.Product.id == product_id))
    ).scalar_one()


@pytest.mark.asyncio
async def test_confirm_reserves_and_blocks_oversell(client, db_session):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    product_id = seed["p1"].id
    customer_id = seed["party1"].id

    await apply_stock_change(
        db_session,
        tenant_id=seed["t1"].id,
        product_id=product_id,
        quantity_delta=10,
        movement_type="stock_in",
        user_id=seed["mgr1"].id,
    )
    await db_session.commit()
    db_session.expire_all()
    on_hand = float((await _product(db_session, product_id)).stock_qty)
    reserve_qty = on_hand - 2  # leave only 2 available after confirm

    created = await ac.post(
        "/api/v1/sales/orders",
        headers=headers,
        json={
            "customer_id": customer_id,
            "items": [{"product_id": product_id, "quantity": reserve_qty, "unit_price": 5}],
        },
    )
    assert created.status_code == 200, created.text
    order_id = created.json()["data"]["id"]

    confirmed = await ac.post(f"/api/v1/sales/orders/{order_id}/confirm", headers=headers)
    assert confirmed.status_code == 200, confirmed.text
    data = confirmed.json()["data"]
    assert data["status"] == "confirmed"
    assert data["reserved_qty_total"] == pytest.approx(reserve_qty)
    assert any(i["reserved_qty"] == pytest.approx(reserve_qty) for i in data["items"])

    db_session.expire_all()
    product = await _product(db_session, product_id)
    assert float(product.stock_qty) == pytest.approx(on_hand)
    assert float(product.reserved_qty) == pytest.approx(reserve_qty)

    blocked = await ac.post(
        "/api/v1/sales/orders",
        headers=headers,
        json={
            "customer_id": customer_id,
            "items": [{"product_id": product_id, "quantity": 5, "unit_price": 5}],
        },
    )
    assert blocked.status_code == 200, blocked.text
    other_id = blocked.json()["data"]["id"]
    fail = await ac.post(f"/api/v1/sales/orders/{other_id}/confirm", headers=headers)
    assert fail.status_code == 409, fail.text
    detail = fail.json()["detail"]
    assert detail["code"] == "INSUFFICIENT_AVAILABLE_STOCK"


@pytest.mark.asyncio
async def test_cancel_releases_reservation(client, db_session):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    product_id = seed["p1"].id

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
            "customer_id": seed["party1"].id,
            "items": [{"product_id": product_id, "quantity": 4, "unit_price": 2}],
        },
    )
    order_id = created.json()["data"]["id"]
    assert (await ac.post(f"/api/v1/sales/orders/{order_id}/confirm", headers=headers)).status_code == 200

    cancelled = await ac.post(f"/api/v1/sales/orders/{order_id}/cancel", headers=headers)
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["data"]["status"] == "cancelled"
    assert cancelled.json()["data"]["reserved_qty_total"] == 0

    db_session.expire_all()
    product = await _product(db_session, product_id)
    assert float(product.reserved_qty) == pytest.approx(0)


@pytest.mark.asyncio
async def test_convert_and_post_consumes_reservation_once(client, db_session):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    product_id = seed["p1"].id

    await apply_stock_change(
        db_session,
        tenant_id=seed["t1"].id,
        product_id=product_id,
        quantity_delta=8,
        movement_type="stock_in",
        user_id=seed["mgr1"].id,
    )
    await db_session.commit()
    customer_id = seed["party1"].id
    db_session.expire_all()
    on_hand = float((await _product(db_session, product_id)).stock_qty)
    qty = 3

    created = await ac.post(
        "/api/v1/sales/orders",
        headers=headers,
        json={
            "customer_id": customer_id,
            "items": [{"product_id": product_id, "quantity": qty, "unit_price": 10}],
        },
    )
    order_id = created.json()["data"]["id"]
    assert (await ac.post(f"/api/v1/sales/orders/{order_id}/confirm", headers=headers)).status_code == 200

    converted = await ac.post(f"/api/v1/sales/orders/{order_id}/convert-invoice", headers=headers)
    assert converted.status_code == 200, converted.text
    invoice_id = converted.json()["data"]["id"]
    assert converted.json()["data"]["status"] == "draft"

    db_session.expire_all()
    product = await _product(db_session, product_id)
    assert float(product.stock_qty) == pytest.approx(on_hand)
    assert float(product.reserved_qty) == pytest.approx(qty)

    posted = await ac.post(f"/api/v1/sales/invoices/{invoice_id}/post", headers=headers)
    assert posted.status_code == 200, posted.text

    db_session.expire_all()
    product = await _product(db_session, product_id)
    assert float(product.stock_qty) == pytest.approx(on_hand - qty)
    assert float(product.reserved_qty) == pytest.approx(0)

    reservations = (
        await db_session.execute(
            select(m.StockReservation).where(m.StockReservation.sales_order_id == order_id)
        )
    ).scalars().all()
    assert reservations
    assert all(r.status == "consumed" for r in reservations)


@pytest.mark.asyncio
async def test_foreign_store_on_order_rejected(client, db_session):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    foreign_store = m.Store(tenant_id=seed["t2"].id, name="Beta Store", code="BST")
    db_session.add(foreign_store)
    await db_session.flush()
    foreign_store_id = foreign_store.id
    await db_session.commit()

    r = await ac.post(
        "/api/v1/sales/orders",
        headers=headers,
        json={
            "customer_id": seed["party1"].id,
            "store_id": foreign_store_id,
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 1}],
        },
    )
    assert r.status_code == 404
