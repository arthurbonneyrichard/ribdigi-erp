"""Cashier selling presence: admin list, tenant isolation, offline duration."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app import models as m
from app.cashier_presence import summarize_devices
from app.rbac import permissions_for_role
from app.security import hash_password
from tests.conftest import auth_headers


def test_offline_duration_uses_offline_since():
    now = datetime(2026, 10, 11, 20, 0, 0)
    device = m.PosDevice(
        tenant_id="t",
        device_id="dev-presence-unit1",
        user_id="cashier-1",
        selling_online=False,
        offline_since=now - timedelta(minutes=12),
        last_seen_at=now - timedelta(minutes=12),
    )
    summary = summarize_devices([device], now)
    assert summary["status"] == "offline"
    assert summary["offline_duration_seconds"] == 12 * 60
    assert summary["offline_since"]


def test_stale_online_heartbeat_counts_as_offline():
    now = datetime(2026, 10, 11, 20, 0, 0)
    device = m.PosDevice(
        tenant_id="t",
        device_id="dev-presence-unit2",
        user_id="cashier-1",
        selling_online=True,
        offline_since=None,
        last_seen_at=now - timedelta(minutes=10),
    )
    summary = summarize_devices([device], now)
    assert summary["status"] == "offline"
    assert summary["offline_duration_seconds"] == 10 * 60


def test_fresh_online_heartbeat_has_no_duration():
    now = datetime(2026, 10, 11, 20, 0, 0)
    device = m.PosDevice(
        tenant_id="t",
        device_id="dev-presence-unit3",
        user_id="cashier-1",
        selling_online=True,
        last_seen_at=now - timedelta(seconds=20),
    )
    summary = summarize_devices([device], now)
    assert summary["status"] == "online"
    assert summary["offline_duration_seconds"] is None


async def _headers(ac, email: str, slug: str):
    return await auth_headers(ac, email=email, tenant_slug=slug)


@pytest.mark.asyncio
async def test_admin_sees_cashier_offline_duration_and_cashier_cannot_list(client, db_session):
    ac, seed = client
    alpha_cashier_id = seed["u1"].id
    cashier = await _headers(ac, "cashier@alpha.example.com", "alpha")
    admin = await _headers(ac, "admin@alpha.example.com", "alpha")
    manager = await _headers(ac, "mgr@alpha.example.com", "alpha")

    beta_admin = m.User(
        tenant_id=seed["t2"].id,
        email="admin@beta.example.com",
        full_name="Beta Admin",
        password_hash=hash_password("SecurePass123!"),
        role="company_admin",
        email_verified=True,
        permissions=permissions_for_role("company_admin"),
        totp_enabled=False,
    )
    db_session.add(beta_admin)
    await db_session.commit()
    beta_admin_h = await _headers(ac, "admin@beta.example.com", "beta")
    beta_cashier = await _headers(ac, "cashier@beta.example.com", "beta")

    denied = await ac.get("/api/v1/users/cashier-presence", headers=cashier)
    assert denied.status_code == 403, denied.text

    beat = await ac.post(
        "/api/v1/pos/devices/heartbeat",
        headers=cashier,
        json={
            "device_id": "dev-alpha-cashier01",
            "selling_online": False,
            "pending_queue_count": 1,
        },
    )
    assert beat.status_code == 200, beat.text
    assert beat.json()["data"]["selling_online"] is False
    assert beat.json()["data"]["offline_since"]

    db_session.expire_all()
    device = (
        await db_session.execute(
            select(m.PosDevice).where(m.PosDevice.device_id == "dev-alpha-cashier01")
        )
    ).scalar_one()
    device.offline_since = datetime.utcnow() - timedelta(minutes=12)
    device.last_seen_at = device.offline_since
    await db_session.commit()

    other = await ac.post(
        "/api/v1/pos/devices/heartbeat",
        headers=beta_cashier,
        json={"device_id": "dev-beta-cashier01", "selling_online": False},
    )
    assert other.status_code == 200, other.text

    listed = await ac.get("/api/v1/users/cashier-presence", headers=admin)
    assert listed.status_code == 200, listed.text
    rows = listed.json()["data"]
    assert [row["full_name"] for row in rows] == ["Alpha Cashier"]
    alpha = rows[0]
    assert alpha["status"] == "offline"
    assert alpha["offline_duration_seconds"] is not None
    assert alpha["offline_duration_seconds"] >= 12 * 60 - 5
    assert alpha["user_id"] == alpha_cashier_id

    mgr = await ac.get("/api/v1/users/cashier-presence", headers=manager)
    assert mgr.status_code == 200, mgr.text
    assert [row["user_id"] for row in mgr.json()["data"]] == [alpha_cashier_id]

    beta_listed = await ac.get("/api/v1/users/cashier-presence", headers=beta_admin_h)
    assert beta_listed.status_code == 200, beta_listed.text
    beta_rows = beta_listed.json()["data"]
    assert [row["full_name"] for row in beta_rows] == ["Beta Cashier"]
    beta_ids = [row["user_id"] for row in beta_rows]
    assert alpha_cashier_id not in beta_ids
    assert beta_rows[0]["status"] == "offline"
    assert beta_rows[0]["offline_duration_seconds"] is not None
