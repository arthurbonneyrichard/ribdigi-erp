"""Pre-launch security audit Phase 2 — High finding regressions (SEC-H1…H5)."""

from __future__ import annotations

from datetime import datetime

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import select

from app import models as m
from app.config import Settings
from app.inventory import get_or_create_warehouse_stock
from app.main import app
from app.middleware import RateLimitMiddleware
from app.rate_limit import rate_limiter
from app.security import create_access_token

pytestmark = pytest.mark.security


@pytest.mark.asyncio
async def test_sec_h1_missing_auth_session_rejects_access_jwt(client, db_session):
    """SEC-H1: JWT with unknown jti must not authorize."""
    ac, seed = client
    token = create_access_token(
        seed["mgr1"].id,
        seed["t1"].id,
        "store_manager",
        jti="no-such-session-jti",
    )
    r = await ac.get(
        "/api/v1/products",
        headers={"Authorization": f"Bearer {token}", "X-Tenant-ID": seed["t1"].id},
    )
    assert r.status_code == 401
    assert "session" in r.text.lower() or "revoked" in r.text.lower()


@pytest.mark.asyncio
async def test_sec_h1_revoked_session_still_rejected(client, db_session):
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
    payload = jwt.get_unverified_claims(token)
    jti = payload["jti"]
    session = (
        await db_session.execute(select(m.AuthSession).where(m.AuthSession.jti == jti))
    ).scalar_one()
    session.revoked_at = datetime.utcnow()
    await db_session.commit()

    r = await ac.get(
        "/api/v1/products",
        headers={"Authorization": f"Bearer {token}", "X-Tenant-ID": seed["t1"].id},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_sec_h3_warehouse_stock_rejects_foreign_product(client, db_session):
    """SEC-H3: foreign-tenant product id must 404 inside stock helper."""
    _ac, seed = client
    wh = m.Warehouse(
        tenant_id=seed["t1"].id,
        company_id=seed["c1"].id,
        name="Audit WH",
        code="AUD-WH",
    )
    db_session.add(wh)
    await db_session.flush()

    with pytest.raises(HTTPException) as exc:
        await get_or_create_warehouse_stock(
            db_session,
            tenant_id=seed["t1"].id,
            warehouse_id=wh.id,
            product_id=seed["p2"].id,  # beta tenant product
        )
    assert exc.value.status_code == 404


def test_sec_h5_cors_allows_workspace_headers():
    cors = None
    for middleware in app.user_middleware:
        if middleware.cls.__name__ == "CORSMiddleware":
            cors = middleware
            break
    assert cors is not None
    headers = cors.kwargs.get("allow_headers") or []
    assert "X-Workspace-Kind" in headers
    assert "X-Company-ID" in headers


def test_sec_h4_xff_ignored_by_default():
    rate_limiter.reset_for_tests()
    mw = RateLimitMiddleware(app)
    from starlette.requests import Request

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "path": "/api/v1/health",
        "raw_path": b"/api/v1/health",
        "query_string": b"",
        "headers": [(b"x-forwarded-for", b"203.0.113.9")],
        "client": ("198.51.100.2", 12345),
        "server": ("test", 80),
        "scheme": "http",
    }
    request = Request(scope)
    # Default TRUST_X_FORWARDED_FOR=false → peer address
    assert mw._client_ip(request) == "198.51.100.2"


def test_sec_h4_xff_honored_when_trusted(monkeypatch):
    monkeypatch.setattr("app.middleware.settings.TRUST_X_FORWARDED_FOR", True)
    mw = RateLimitMiddleware(app)
    from starlette.requests import Request

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "path": "/api/v1/health",
        "raw_path": b"/api/v1/health",
        "query_string": b"",
        "headers": [(b"x-forwarded-for", b"203.0.113.9, 10.0.0.1")],
        "client": ("198.51.100.2", 12345),
        "server": ("test", 80),
        "scheme": "http",
    }
    request = Request(scope)
    assert mw._client_ip(request) == "203.0.113.9"


def test_sec_h2_metrics_open_when_auth_not_required():
    rate_limiter.reset_for_tests()
    client = TestClient(app)
    assert client.get("/api/v1/metrics").status_code == 200


def test_sec_h2_metrics_requires_bearer_when_configured(monkeypatch):
    rate_limiter.reset_for_tests()
    monkeypatch.setattr("app.config.settings.METRICS_REQUIRE_AUTH", True)
    monkeypatch.setattr("app.config.settings.METRICS_BEARER_TOKEN", "metrics-token-16chars")
    # api.metrics_endpoint reads settings from app.config.settings
    monkeypatch.setattr("app.api.settings.METRICS_REQUIRE_AUTH", True)
    monkeypatch.setattr("app.api.settings.METRICS_BEARER_TOKEN", "metrics-token-16chars")
    client = TestClient(app)
    assert client.get("/api/v1/metrics").status_code == 401
    ok = client.get(
        "/api/v1/metrics",
        headers={"Authorization": "Bearer metrics-token-16chars"},
    )
    assert ok.status_code == 200
    assert "ribdigi_up 1" in ok.text


def test_sec_h2_production_validator_requires_metrics_token():
    with pytest.raises(Exception) as exc:
        Settings(
            APP_ENV="production",
            JWT_SECRET_KEY="x" * 32,
            DEBUG=False,
            CORS_ORIGINS="https://app.example.com",
            RATE_LIMIT_ENABLED=True,
            EMAIL_ENABLED=False,
            SMS_ENABLED=False,
            METRICS_ENABLED=True,
            METRICS_REQUIRE_AUTH=True,
            METRICS_BEARER_TOKEN="short",
        )
    assert "METRICS" in str(exc.value).upper()


def test_sec_h2_production_env_example_documents_metrics_auth():
    from pathlib import Path

    text = (Path(__file__).resolve().parents[2] / ".env.production.example").read_text(
        encoding="utf-8"
    )
    assert "METRICS_REQUIRE_AUTH=true" in text
    assert "METRICS_BEARER_TOKEN=" in text
    assert "TRUST_X_FORWARDED_FOR=true" in text
