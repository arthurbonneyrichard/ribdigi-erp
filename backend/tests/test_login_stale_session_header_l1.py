"""Login must succeed with only workspace slug in the body (no leftover session)."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.asyncio
async def test_login_succeeds_without_x_tenant_header(client):
    ac, _seed = client
    r = await ac.post(
        "/api/v1/auth/login",
        json={
            "email": "cashier@alpha.example.com",
            "password": "SecurePass123!",
            "tenant_id": "alpha",
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["access_token"]
    assert data["user"]["tenant_id"] == _seed["t1"].id


@pytest.mark.asyncio
async def test_login_ignores_stale_foreign_x_tenant_header(client):
    """Platform leftover X-Tenant-ID must not block signing into another workspace."""
    ac, seed = client
    r = await ac.post(
        "/api/v1/auth/login",
        headers={"X-Tenant-ID": seed["t2"].id},
        json={
            "email": "cashier@alpha.example.com",
            "password": "SecurePass123!",
            "tenant_id": "alpha",
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["user"]["tenant_id"] == seed["t1"].id


def test_login_client_omits_stale_session_headers():
    api_ts = (ROOT / "frontend/lib/api.ts").read_text(encoding="utf-8")
    login_ts = (ROOT / "frontend/app/page.tsx").read_text(encoding="utf-8")
    assert "isPublicAuthPath" in api_ts
    assert "path.startsWith('/auth/login')" in api_ts
    assert "unreachableApiMessage" in api_ts
    assert "invalidateMeCache" in login_ts
    assert "unreachableApiMessage" in login_ts
    nxt = (ROOT / "frontend/next.config.mjs").read_text(encoding="utf-8")
    assert "source: '/api/v1/:path*'" in nxt
    assert "apiRoot" in api_ts
    assert "typeof window !== 'undefined') return '/api/v1'" in api_ts
