"""Offline owner alerts API tests."""

from __future__ import annotations

from datetime import datetime, timedelta

import pyotp
import pytest

from app import models as m
from tests.conftest import auth_headers


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_offline_alerts_never_bound_device(client):
    ac, seed = client
    headers = await _super(ac, seed)
    created = await ac.post(
        "/api/v1/offline/devices",
        headers=headers,
        json={"name": "Unbound Till", "platform": "web"},
    )
    assert created.status_code == 200
    device_id = created.json()["data"]["id"]

    r = await ac.get("/api/v1/offline/alerts", headers=headers)
    assert r.status_code == 200
    body = r.json()["data"]
    codes = [a["code"] for a in body["alerts"]]
    assert "OFFLINE_DEVICE_NEVER_BOUND" in codes
    bound = [a for a in body["alerts"] if a.get("device_id") == device_id]
    assert any(a["code"] == "OFFLINE_DEVICE_NEVER_BOUND" for a in bound)


@pytest.mark.asyncio
async def test_offline_alerts_expired_envelope(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)
    created = await ac.post(
        "/api/v1/offline/devices",
        headers=headers,
        json={"name": "Expired Till", "platform": "web"},
    )
    device_id = created.json()["data"]["id"]
    bind = await ac.post(f"/api/v1/offline/devices/{device_id}/bind", headers=headers, json={})
    assert bind.status_code == 200

    row = await db_session.get(m.OfflineDevice, device_id)
    row.offline_authorized_until = datetime.utcnow() - timedelta(hours=1)
    await db_session.commit()

    r = await ac.get("/api/v1/offline/alerts", headers=headers)
    assert r.status_code == 200
    alerts = r.json()["data"]["alerts"]
    assert any(
        a["code"] == "OFFLINE_ENVELOPE_EXPIRED" and a["device_id"] == device_id for a in alerts
    )


@pytest.mark.asyncio
async def test_offline_alerts_open_conflicts(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)
    db_session.add(
        m.SyncConflict(
            tenant_id=seed["t1"].id,
            op_type="pos_sale",
            client_payload={"x": 1},
            server_snapshot={"x": 2},
            status="open",
        )
    )
    await db_session.commit()

    r = await ac.get("/api/v1/offline/alerts", headers=headers)
    assert r.status_code == 200
    codes = [a["code"] for a in r.json()["data"]["alerts"]]
    assert "SYNC_CONFLICTS_OPEN" in codes
