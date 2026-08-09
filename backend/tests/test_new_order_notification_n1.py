"""Stage 4 N1: new_order notification on sales-order create (BR-15.1)."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app import models as m
from app.notifications import update_preferences
from tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_create_order_emits_new_order_notification(client, db_session):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    tenant_id = seed["t1"].id

    created = await ac.post(
        "/api/v1/sales/orders",
        headers=headers,
        json={
            "customer_id": seed["party1"].id,
            "items": [
                {
                    "product_id": seed["p1"].id,
                    "quantity": 1,
                    "unit_price": 10,
                    "tax_rate": 0,
                    "discount": 0,
                }
            ],
        },
    )
    assert created.status_code == 200, created.text
    order = created.json()["data"]
    order_id = order["id"]

    notes = (
        await db_session.execute(
            select(m.Notification).where(
                m.Notification.tenant_id == tenant_id,
                m.Notification.category == "new_order",
                m.Notification.entity_id == order_id,
            )
        )
    ).scalars().all()
    assert len(notes) >= 1
    assert "New sales order" in notes[0].title
    assert order["order_number"] in notes[0].message

    listed = await ac.get("/api/v1/notifications?group=orders", headers=headers)
    assert listed.status_code == 200
    cats = {n["category"] for n in listed.json()["data"]}
    assert "new_order" in cats
    assert all(n.get("group") == "orders" for n in listed.json()["data"] if n["category"] == "new_order")


@pytest.mark.asyncio
async def test_confirm_order_emits_new_order_and_prefs_honored(client, db_session):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    tenant_id = seed["t1"].id
    uid = seed["mgr1"].id

    seed["p1"].stock_qty = 100
    await db_session.commit()

    created = await ac.post(
        "/api/v1/sales/orders",
        headers=headers,
        json={
            "customer_id": seed["party1"].id,
            "items": [
                {
                    "product_id": seed["p1"].id,
                    "quantity": 1,
                    "unit_price": 5,
                    "tax_rate": 0,
                    "discount": 0,
                }
            ],
        },
    )
    assert created.status_code == 200, created.text
    order_id = created.json()["data"]["id"]

    confirmed = await ac.post(f"/api/v1/sales/orders/{order_id}/confirm", headers=headers)
    assert confirmed.status_code == 200, confirmed.text

    notes = (
        await db_session.execute(
            select(m.Notification).where(
                m.Notification.tenant_id == tenant_id,
                m.Notification.category == "new_order",
                m.Notification.entity_id == order_id,
            )
        )
    ).scalars().all()
    titles = {n.title for n in notes}
    assert "New sales order" in titles
    assert "Sales order confirmed" in titles

    # Targeted user with dashboard channel off should not get a personal note
    await update_preferences(
        db_session,
        tenant_id,
        uid,
        {"new_order": {"dashboard": False, "email": False, "sms": False}},
    )
    await db_session.commit()

    from app.notifications import create_notification

    skipped = await create_notification(
        db_session,
        tenant_id=tenant_id,
        user_id=uid,
        category="new_order",
        title="Should skip",
        message="Dashboard disabled",
        entity_type="sales_order",
        entity_id=order_id,
    )
    assert skipped is None


@pytest.mark.asyncio
async def test_new_order_notification_tenant_isolated(client, db_session):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    foreign = m.Notification(
        tenant_id=seed["t2"].id,
        category="new_order",
        title="Beta order",
        message="Should not leak",
        status="unread",
        entity_type="sales_order",
        entity_id=None,
    )
    db_session.add(foreign)
    await db_session.commit()

    listed = await ac.get("/api/v1/notifications?category=new_order", headers=headers)
    assert listed.status_code == 200
    titles = {n["title"] for n in listed.json()["data"]}
    assert "Beta order" not in titles
