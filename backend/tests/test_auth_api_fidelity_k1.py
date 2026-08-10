"""Stage 19 K1: Auth API fidelity — JWT login/refresh, API keys, rate limits (BR-18.1)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest
from fastapi.testclient import TestClient

from app import catalog_meta as catalog_meta_svc
from app.main import app
from app.middleware import AUTH_PATH_PREFIXES
from app.rate_limit import rate_limiter
from tests.conftest import auth_headers

pytestmark = pytest.mark.security

ROOT = Path(__file__).resolve().parents[2]


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_jwt_login_issues_bearer_pair(client):
    ac, seed = client
    res = await ac.post(
        "/api/v1/auth/login",
        json={
            "email": "mgr@alpha.example.com",
            "password": "SecurePass123!",
            "tenant_id": "alpha",
        },
    )
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["token_type"] == "Bearer"
    assert data["access_token"]
    assert data["refresh_token"]
    assert data["expires_in"] > 0
    assert data["user"]["tenant_id"] == seed["t1"].id
    assert data["user"]["email"] == "mgr@alpha.example.com"

    me = await ac.get(
        "/api/v1/me",
        headers={
            "Authorization": f"Bearer {data['access_token']}",
            "X-Tenant-ID": seed["t1"].id,
        },
    )
    assert me.status_code == 200, me.text
    assert me.json()["data"]["email"] == "mgr@alpha.example.com"


@pytest.mark.asyncio
async def test_token_refresh_rotates_and_invalidates_old(client):
    ac, seed = client
    login = await ac.post(
        "/api/v1/auth/login",
        json={
            "email": "mgr@alpha.example.com",
            "password": "SecurePass123!",
            "tenant_id": "alpha",
        },
    )
    assert login.status_code == 200, login.text
    old_refresh = login.json()["data"]["refresh_token"]
    old_access = login.json()["data"]["access_token"]

    refreshed = await ac.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": old_refresh},
    )
    assert refreshed.status_code == 200, refreshed.text
    body = refreshed.json()["data"]
    assert body["token_type"] == "Bearer"
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["refresh_token"] != old_refresh
    assert body["access_token"] != old_access

    reuse = await ac.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": old_refresh},
    )
    assert reuse.status_code == 401

    me = await ac.get(
        "/api/v1/me",
        headers={
            "Authorization": f"Bearer {body['access_token']}",
            "X-Tenant-ID": seed["t1"].id,
        },
    )
    assert me.status_code == 200, me.text


@pytest.mark.asyncio
async def test_logout_revokes_access_session(client):
    ac, seed = client
    login = await ac.post(
        "/api/v1/auth/login",
        json={
            "email": "mgr@alpha.example.com",
            "password": "SecurePass123!",
            "tenant_id": "alpha",
        },
    )
    assert login.status_code == 200, login.text
    token = login.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}", "X-Tenant-ID": seed["t1"].id}

    logged_out = await ac.post("/api/v1/auth/logout", headers=headers, json={})
    assert logged_out.status_code == 200, logged_out.text

    me = await ac.get("/api/v1/me", headers=headers)
    assert me.status_code == 401


@pytest.mark.asyncio
async def test_api_key_path_remains_green(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    await catalog_meta_svc.ensure_default_catalog(db_session, seed["t1"].id)
    await db_session.commit()

    created = await ac.post(
        "/api/v1/api-keys",
        headers=headers,
        json={
            "name": "Stage19 K1 integrator",
            "permissions": {"inventory": ["read"]},
        },
    )
    assert created.status_code == 200, created.text
    secret = created.json()["data"]["api_key"]
    assert secret.startswith("rdk_")

    products = await ac.get(
        "/api/v1/products",
        headers={"X-API-Key": secret, "X-Tenant-ID": seed["t1"].id},
    )
    assert products.status_code == 200, products.text


def test_rate_limit_headers_and_tenant_buckets(monkeypatch):
    """BR-18.1: X-RateLimit-* headers; buckets isolate by X-Tenant-ID."""
    rate_limiter.reset_for_tests()
    monkeypatch.setattr("app.middleware.settings.RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr("app.middleware.settings.RATE_LIMIT_PER_MINUTE", 2)
    monkeypatch.setattr("app.middleware.settings.RATE_LIMIT_AUTH_PER_MINUTE", 2)

    assert any(p.endswith("/auth/refresh") for p in AUTH_PATH_PREFIXES)

    client = TestClient(app)
    first = client.get("/api/v1/health", headers={"X-Tenant-ID": "tenant-alpha"})
    assert first.status_code == 200
    assert "X-RateLimit-Limit" in first.headers
    assert "X-RateLimit-Remaining" in first.headers
    assert "X-RateLimit-Backend" in first.headers

    assert client.get("/api/v1/health", headers={"X-Tenant-ID": "tenant-alpha"}).status_code == 200
    blocked = client.get("/api/v1/health", headers={"X-Tenant-ID": "tenant-alpha"})
    assert blocked.status_code == 429
    assert blocked.json()["detail"] == "RATE_LIMIT_EXCEEDED"
    assert "Retry-After" in blocked.headers
    assert blocked.headers.get("X-RateLimit-Remaining") == "0"

    other = client.get("/api/v1/health", headers={"X-Tenant-ID": "tenant-beta"})
    assert other.status_code == 200
    assert int(other.headers.get("X-RateLimit-Remaining", "0")) >= 0


def test_br18_1_and_plan_synced():
    br = (ROOT / "docs" / "BUSINESS_REQUIREMENTS_DOCUMENT.md").read_text(encoding="utf-8")
    section = br.split("#### BR-18.1 Authentication API")[1].split("#### BR-18.2")[0]
    assert "[x] OAuth2 / JWT token generation" in section
    assert "[x] Token refresh endpoint" in section
    assert "[x] API key support for service integrations" in section
    assert "[x] Rate limiting per tenant" in section
    assert "Stage 19 K1" in section

    plan = (ROOT / "docs" / "STAGE_19_PLAN.md").read_text(encoding="utf-8")
    k1_line = [ln for ln in plan.splitlines() if "| **K1**" in ln][0]
    assert "COMPLETE" in k1_line
    assert "test_auth_api_fidelity_k1.py" in plan
