"""Stage 7 K2: API key usage statistics (requests + per-day series)."""

from __future__ import annotations

import pyotp
import pytest
from sqlalchemy import select

from app import models as m
from tests.conftest import auth_headers


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_api_key_usage_increments_and_series(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)

    created = await ac.post(
        "/api/v1/api-keys",
        headers=headers,
        json={"name": "Usage key", "permissions": {"inventory": ["read"], "sales": ["read"]}},
    )
    assert created.status_code == 200, created.text
    key_id = created.json()["data"]["id"]
    secret = created.json()["data"]["api_key"]
    assert created.json()["data"]["request_count"] == 0

    for _ in range(3):
        r = await ac.get(
            "/api/v1/products",
            headers={"X-API-Key": secret, "X-Tenant-ID": seed["t1"].id},
        )
        assert r.status_code == 200, r.text

    usage = await ac.get(f"/api/v1/api-keys/{key_id}/usage?days=30", headers=headers)
    assert usage.status_code == 200, usage.text
    body = usage.json()["data"]
    assert body["api_key_id"] == key_id
    assert body["total_requests"] == 3
    assert body["period_requests"] == 3
    assert body["days"] == 30
    assert len(body["series"]) == 30
    assert body["series"][-1]["requests"] == 3
    assert body["last_used_at"] is not None

    listed = await ac.get("/api/v1/api-keys", headers=headers)
    assert listed.status_code == 200
    row = next(r for r in listed.json()["data"] if r["id"] == key_id)
    assert row["request_count"] == 3
    assert row["last_used_at"] is not None

    daily = (
        await db_session.execute(
            select(m.ApiKeyUsageDaily).where(
                m.ApiKeyUsageDaily.tenant_id == seed["t1"].id,
                m.ApiKeyUsageDaily.api_key_id == key_id,
            )
        )
    ).scalars().all()
    assert len(daily) == 1
    assert daily[0].request_count == 3


@pytest.mark.asyncio
async def test_api_key_usage_tenant_isolation(client):
    ac, seed = client
    headers = await _admin(ac, seed)
    created = await ac.post(
        "/api/v1/api-keys",
        headers=headers,
        json={"name": "Alpha only", "permissions": {"inventory": ["read"]}},
    )
    key_id = created.json()["data"]["id"]

    beta = await auth_headers(ac, email="cashier@beta.example.com", tenant_slug="beta")
    # Cashier lacks admin role
    denied = await ac.get(f"/api/v1/api-keys/{key_id}/usage", headers=beta)
    assert denied.status_code == 403

    # Cross-tenant: beta admin cannot see alpha key
    # Seed has no beta admin with 2FA — use alpha admin against wrong id shape via tenant header swap is blocked by JWT tenant.
    missing = await ac.get(
        f"/api/v1/api-keys/{key_id}/usage",
        headers={**headers, "X-Tenant-ID": seed["t2"].id},
    )
    # JWT tenant wins; X-Tenant-ID mismatch → 403
    assert missing.status_code == 403


@pytest.mark.asyncio
async def test_api_key_usage_days_clamped(client):
    ac, seed = client
    headers = await _admin(ac, seed)
    created = await ac.post(
        "/api/v1/api-keys",
        headers=headers,
        json={"name": "Clamp", "permissions": {"reports": ["read"]}},
    )
    key_id = created.json()["data"]["id"]
    wide = await ac.get(f"/api/v1/api-keys/{key_id}/usage?days=999", headers=headers)
    assert wide.status_code == 200
    assert wide.json()["data"]["days"] == 90
    assert len(wide.json()["data"]["series"]) == 90
