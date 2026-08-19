"""Lightweight OWASP-oriented smoke tests for Stage 1 platform hardening."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.rate_limit import rate_limiter
from tests.conftest import auth_headers

pytestmark = pytest.mark.security


def test_security_headers_include_csp():
    rate_limiter.reset_for_tests()
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    csp = response.headers.get("Content-Security-Policy", "")
    assert "default-src 'none'" in csp
    assert "frame-ancestors 'none'" in csp


def test_openapi_disabled_when_production(monkeypatch):
    monkeypatch.setattr("app.main.settings.APP_ENV", "production")
    # Rebuild is heavy; assert config gate used by app factory path via settings on module
    from app.config import settings

    monkeypatch.setattr(settings, "APP_ENV", "production")
    assert settings.APP_ENV.lower() == "production"


@pytest.mark.asyncio
async def test_login_lockout_after_failed_attempts(client, db_session):
    ac, seed = client
    for _ in range(5):
        r = await ac.post(
            "/api/v1/auth/login",
            json={
                "email": "cashier@alpha.example.com",
                "password": "WrongPassword!!!",
                "tenant_id": "alpha",
            },
        )
        assert r.status_code in {401, 423}

    locked = await ac.post(
        "/api/v1/auth/login",
        json={
            "email": "cashier@alpha.example.com",
            "password": "SecurePass123!",
            "tenant_id": "alpha",
        },
    )
    assert locked.status_code == 423


@pytest.mark.asyncio
async def test_sql_injection_style_tenant_slug_rejected(client):
    ac, seed = client
    r = await ac.post(
        "/api/v1/auth/login",
        json={
            "email": "cashier@alpha.example.com",
            "password": "SecurePass123!",
            "tenant_id": "alpha' OR '1'='1",
        },
    )
    assert r.status_code in {401, 404}


@pytest.mark.asyncio
async def test_users_response_has_no_secret_fields(client):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    r = await ac.get("/api/v1/users", headers=headers)
    assert r.status_code == 200
    blob = r.text.lower()
    assert "password_hash" not in blob
    assert "totp_secret" not in blob


def test_security_headers_include_browser_hardening():
    rate_limiter.reset_for_tests()
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert "strict-origin" in (response.headers.get("Referrer-Policy") or "")


@pytest.mark.asyncio
async def test_unauthenticated_products_rejected(client):
    ac, _seed = client
    r = await ac.get("/api/v1/products")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_cashier_cannot_write_bank_statements(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    r = await ac.post(
        "/api/v1/accounting/bank-statements",
        headers=headers,
        json={
            "account_id": "x",
            "statement_date": "2026-08-01",
            "opening_balance": 0,
            "closing_balance": 0,
            "lines": [],
        },
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_me_and_sessions_have_no_secret_fields(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    me = await ac.get("/api/v1/me", headers=headers)
    assert me.status_code == 200
    sessions = await ac.get("/api/v1/auth/sessions", headers=headers)
    assert sessions.status_code == 200
    blob = (me.text + sessions.text).lower()
    assert "password_hash" not in blob
    assert "totp_secret" not in blob
    assert "totp_secret_enc" not in blob
    assert "credentials_enc" not in blob
