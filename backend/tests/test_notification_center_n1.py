"""Notification center panel APIs (BR-4.4 / BR-15.2)."""

from __future__ import annotations

import pyotp
import pytest

from app.notifications import create_notification
from tests.conftest import auth_headers


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_mark_unread_round_trip_and_category_limit(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    tid = seed["t1"].id
    uid = seed["super"].id

    n1 = await create_notification(
        db_session,
        tenant_id=tid,
        user_id=uid,
        category="low_stock",
        title="Center stock alert",
        message="Reorder soon",
    )
    n2 = await create_notification(
        db_session,
        tenant_id=tid,
        user_id=uid,
        category="system",
        title="Center system ping",
        message="Hello panel",
    )
    assert n1 and n2
    await db_session.commit()

    listed = await ac.get(
        "/api/v1/notifications?status=unread&category=low_stock&limit=5",
        headers=headers,
    )
    assert listed.status_code == 200, listed.text
    rows = listed.json()["data"] or []
    assert any(r["id"] == n1.id for r in rows)
    assert all(r["category"] == "low_stock" for r in rows)
    assert not any(r["id"] == n2.id for r in rows)

    limited = await ac.get("/api/v1/notifications?limit=1", headers=headers)
    assert limited.status_code == 200
    assert len(limited.json()["data"] or []) <= 1

    read = await ac.patch(f"/api/v1/notifications/{n1.id}/read", headers=headers)
    assert read.status_code == 200, read.text
    assert read.json()["data"]["status"] == "read"

    unread_count = await ac.get("/api/v1/notifications/unread-count", headers=headers)
    assert unread_count.status_code == 200
    before = int(unread_count.json()["data"]["count"])

    unread = await ac.patch(f"/api/v1/notifications/{n1.id}/unread", headers=headers)
    assert unread.status_code == 200, unread.text
    assert unread.json()["data"]["status"] == "unread"

    after = await ac.get("/api/v1/notifications/unread-count", headers=headers)
    assert after.status_code == 200
    assert int(after.json()["data"]["count"]) == before + 1

    again = await ac.get(
        "/api/v1/notifications?status=unread&category=low_stock",
        headers=headers,
    )
    assert again.status_code == 200
    assert any(r["id"] == n1.id and r["status"] == "unread" for r in again.json()["data"])
