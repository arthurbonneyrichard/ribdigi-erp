"""Stage 1 F18 — notifications panel: groups, unread toggle, 90-day history (BR-4.4)."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app import models as m
from app.notifications import HISTORY_DAYS, category_group, create_notification
from tests.conftest import auth_headers


def test_category_groups_cover_br44_buckets():
    assert category_group("low_stock") == "stock"
    assert category_group("purchase_received") == "orders"
    assert category_group("payment_due") == "payments"
    assert category_group("security") == "system"
    assert HISTORY_DAYS == 90


@pytest.mark.asyncio
async def test_notifications_group_filter_mark_unread_and_history_window(client, db_session):
    ac, seed = client
    tid = seed["t1"].id
    uid = seed["mgr1"].id
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    stock = await create_notification(
        db_session,
        tenant_id=tid,
        user_id=uid,
        category="low_stock",
        title="Low Stock Alert",
        message="Widget is low",
    )
    pay = await create_notification(
        db_session,
        tenant_id=tid,
        user_id=uid,
        category="payment_due",
        title="Payment Due",
        message="Invoice overdue",
    )
    old = m.Notification(
        tenant_id=tid,
        user_id=uid,
        category="system",
        title="Ancient",
        message="Older than 90 days",
        status="unread",
        created_at=datetime.utcnow() - timedelta(days=HISTORY_DAYS + 5),
    )
    db_session.add(old)
    await db_session.commit()
    assert stock and pay

    listed = await ac.get("/api/v1/notifications?status=unread", headers=headers)
    assert listed.status_code == 200, listed.text
    rows = listed.json()["data"]
    titles = {r["title"] for r in rows}
    assert "Low Stock Alert" in titles
    assert "Payment Due" in titles
    assert "Ancient" not in titles
    stock_row = next(r for r in rows if r["title"] == "Low Stock Alert")
    assert stock_row["group"] == "stock"
    assert stock_row["status"] == "unread"

    stock_only = await ac.get("/api/v1/notifications?group=stock", headers=headers)
    assert stock_only.status_code == 200, stock_only.text
    stock_titles = {r["title"] for r in stock_only.json()["data"]}
    assert "Low Stock Alert" in stock_titles
    assert "Payment Due" not in stock_titles

    bad = await ac.get("/api/v1/notifications?group=nonsense", headers=headers)
    assert bad.status_code == 400

    read = await ac.patch(f"/api/v1/notifications/{stock.id}/read", headers=headers)
    assert read.status_code == 200, read.text
    assert read.json()["data"]["status"] == "read"

    unread = await ac.patch(f"/api/v1/notifications/{stock.id}/unread", headers=headers)
    assert unread.status_code == 200, unread.text
    assert unread.json()["data"]["status"] == "unread"

    count = await ac.get("/api/v1/notifications/unread-count", headers=headers)
    assert count.status_code == 200
    assert count.json()["data"]["count"] >= 2
