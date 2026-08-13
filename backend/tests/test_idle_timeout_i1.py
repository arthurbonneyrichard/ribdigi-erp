"""Tenant-configurable idle session timeout (BR-19.3)."""

from __future__ import annotations

import pyotp
import pytest
from fastapi import HTTPException

from app import models as m
from app.tenants import serialize_tenant, update_profile
from tests.conftest import auth_headers


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


def test_serialize_tenant_idle_timeout_default():
    tenant = m.Tenant(slug="idle", company_name="Idle Co", status="active")
    data = serialize_tenant(tenant)
    assert data["inactivity_timeout_minutes"] == 30


@pytest.mark.asyncio
async def test_update_profile_idle_timeout_bounds(db_session):
    row = m.Tenant(slug="idle-unit", company_name="Unit Idle", status="active")
    db_session.add(row)
    await db_session.flush()

    updated = await update_profile(db_session, row, inactivity_timeout_minutes=45)
    assert updated.inactivity_timeout_minutes == 45

    with pytest.raises(HTTPException) as low:
        await update_profile(db_session, updated, inactivity_timeout_minutes=4)
    assert low.value.status_code == 400

    with pytest.raises(HTTPException) as high:
        await update_profile(db_session, updated, inactivity_timeout_minutes=481)
    assert high.value.status_code == 400


@pytest.mark.asyncio
async def test_idle_timeout_patch_get_me_and_isolation(client):
    ac, seed = client
    headers = await _admin(ac, seed)

    got = await ac.get("/api/v1/tenants/me", headers=headers)
    assert got.status_code == 200
    assert got.json()["data"]["inactivity_timeout_minutes"] == 30

    patched = await ac.patch(
        "/api/v1/tenants/me",
        headers=headers,
        json={"inactivity_timeout_minutes": 15},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["data"]["inactivity_timeout_minutes"] == 15

    again = await ac.get("/api/v1/tenants/me", headers=headers)
    assert again.json()["data"]["inactivity_timeout_minutes"] == 15

    me = await ac.get("/api/v1/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["data"]["inactivity_timeout_minutes"] == 15

    bad = await ac.patch(
        "/api/v1/tenants/me",
        headers=headers,
        json={"inactivity_timeout_minutes": 2},
    )
    assert bad.status_code in {400, 422}

    foreign = await ac.get(
        "/api/v1/tenants/me",
        headers={**headers, "X-Tenant-ID": seed["t2"].id},
    )
    assert foreign.status_code == 403
