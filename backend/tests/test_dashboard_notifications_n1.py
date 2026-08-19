"""Stage 21 N1: Dashboard notifications panel fidelity (BR-4.4)."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pyotp
import pytest

from app import models as m
from app.notifications import HISTORY_DAYS, VALID_CATEGORY_GROUPS, category_group, create_notification
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


def test_notification_groups_and_history_constant():
    assert HISTORY_DAYS == 90
    assert VALID_CATEGORY_GROUPS == {"stock", "orders", "payments", "system"}
    assert category_group("low_stock") == "stock"
    assert category_group("new_order") == "orders"
    assert category_group("payment_due") == "payments"
    assert category_group("system") == "system"


@pytest.mark.asyncio
async def test_dashboard_notifications_panel_fidelity(client, db_session):
    """BR-4.4: unread count, categories/groups, mark read/unread, 90-day history."""
    ac, seed = client
    tid = seed["t1"].id
    uid = seed["super"].id
    headers = await _super(ac, seed)

    stock = await create_notification(
        db_session,
        tenant_id=tid,
        user_id=uid,
        category="low_stock",
        title="N1 Low Stock",
        message="SKU low",
    )
    orders = await create_notification(
        db_session,
        tenant_id=tid,
        user_id=uid,
        category="new_order",
        title="N1 New Order",
        message="SO received",
    )
    payments = await create_notification(
        db_session,
        tenant_id=tid,
        user_id=uid,
        category="payment_due",
        title="N1 Payment Due",
        message="Invoice due",
    )
    system = await create_notification(
        db_session,
        tenant_id=tid,
        user_id=uid,
        category="system",
        title="N1 System",
        message="System notice",
    )
    ancient = m.Notification(
        tenant_id=tid,
        user_id=uid,
        category="system",
        title="N1 Ancient",
        message="Outside 90-day window",
        status="unread",
        created_at=datetime.utcnow() - timedelta(days=HISTORY_DAYS + 5),
    )
    db_session.add(ancient)
    await db_session.commit()
    assert stock and orders and payments and system

    listed = await ac.get("/api/v1/notifications?status=unread", headers=headers)
    assert listed.status_code == 200, listed.text
    rows = listed.json()["data"]
    by_title = {r["title"]: r for r in rows}
    assert "N1 Low Stock" in by_title
    assert "N1 New Order" in by_title
    assert "N1 Payment Due" in by_title
    assert "N1 System" in by_title
    assert "N1 Ancient" not in by_title
    assert by_title["N1 Low Stock"]["group"] == "stock"
    assert by_title["N1 New Order"]["group"] == "orders"
    assert by_title["N1 Payment Due"]["group"] == "payments"
    assert by_title["N1 System"]["group"] == "system"

    for group, title in (
        ("stock", "N1 Low Stock"),
        ("orders", "N1 New Order"),
        ("payments", "N1 Payment Due"),
        ("system", "N1 System"),
    ):
        filtered = await ac.get(f"/api/v1/notifications?group={group}", headers=headers)
        assert filtered.status_code == 200, filtered.text
        titles = {r["title"] for r in filtered.json()["data"]}
        assert title in titles
        assert all(r["group"] == group for r in filtered.json()["data"] if r["title"].startswith("N1 "))

    bad = await ac.get("/api/v1/notifications?group=nonsense", headers=headers)
    assert bad.status_code == 400

    count = await ac.get("/api/v1/notifications/unread-count", headers=headers)
    assert count.status_code == 200, count.text
    assert int(count.json()["data"]["count"]) >= 4

    read = await ac.patch(f"/api/v1/notifications/{stock.id}/read", headers=headers)
    assert read.status_code == 200, read.text
    assert read.json()["data"]["status"] == "read"

    after_read = await ac.get("/api/v1/notifications/unread-count", headers=await _super(ac, seed))
    assert after_read.status_code == 200
    assert int(after_read.json()["data"]["count"]) >= 3

    unread = await ac.patch(
        f"/api/v1/notifications/{stock.id}/unread",
        headers=await _super(ac, seed),
    )
    assert unread.status_code == 200, unread.text
    assert unread.json()["data"]["status"] == "unread"

    history = await ac.get("/api/v1/notifications", headers=await _super(ac, seed))
    assert history.status_code == 200, history.text
    hist_titles = {r["title"] for r in history.json()["data"]}
    assert "N1 Low Stock" in hist_titles
    assert "N1 Ancient" not in hist_titles


def test_br_4_4_and_plan_synced():
    br = (ROOT / "docs" / "BUSINESS_REQUIREMENTS_DOCUMENT.md").read_text(encoding="utf-8")
    s44 = br.split("#### BR-4.4 Notifications Panel")[1].split("---")[0]
    assert "[x] Display unread notification count" in s44
    assert "[x] Categorized notifications" in s44
    assert "[x] Mark as read/unread" in s44
    assert "[x] Notification history (last 90 days)" in s44
    assert "Stage 21 N1" in s44
    assert "test_dashboard_notifications_n1.py" in s44

    plan = (ROOT / "docs" / "STAGE_21_PLAN.md").read_text(encoding="utf-8")
    n1_line = [ln for ln in plan.splitlines() if "| **N1**" in ln][0]
    assert "COMPLETE" in n1_line
    assert "test_dashboard_notifications_n1.py" in plan
