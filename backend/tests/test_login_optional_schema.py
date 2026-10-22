"""Login must still issue a session when optional audit/webhook tables are absent.

Those writes are not required to authenticate. A database behind Alembic head
used to abort POST /auth/login with HTTP 500 after the password check.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from app import schema_compat


@pytest.mark.asyncio
async def test_login_survives_missing_audit_webhook_and_passkey_tables(client, db_engine):
    ac, _seed = client
    async with db_engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS webhook_deliveries"))
        await conn.execute(text("DROP TABLE IF EXISTS webhook_endpoints"))
        await conn.execute(text("DROP TABLE IF EXISTS webauthn_credentials"))
        await conn.execute(text("DROP TABLE IF EXISTS audit_logs"))
    schema_compat.clear_column_cache()

    missing_tenant = await ac.post(
        "/api/v1/auth/login",
        json={
            "email": "cashier@alpha.example.com",
            "password": "SecurePass123!",
            "tenant_id": "no-such-tenant",
            "totp_code": None,
        },
    )
    assert missing_tenant.status_code == 404, missing_tenant.text
    assert missing_tenant.json()["detail"] == "Tenant not found"
    assert "traceback" not in missing_tenant.text.lower()
    assert "password" not in missing_tenant.text.lower()

    wrong_password = await ac.post(
        "/api/v1/auth/login",
        json={
            "email": "cashier@alpha.example.com",
            "password": "WrongPass123!",
            "tenant_id": "alpha",
            "totp_code": None,
        },
    )
    assert wrong_password.status_code == 401, wrong_password.text
    assert wrong_password.json()["detail"] == "Invalid credentials"
    assert "SecurePass123" not in wrong_password.text
    assert "traceback" not in wrong_password.text.lower()

    ok = await ac.post(
        "/api/v1/auth/login",
        json={
            "email": "cashier@alpha.example.com",
            "password": "SecurePass123!",
            "tenant_id": "alpha",
            "totp_code": None,
        },
    )
    assert ok.status_code == 200, ok.text
    data = ok.json()["data"]
    assert data["access_token"]
    assert data["refresh_token"]
    assert data["user"]["email"] == "cashier@alpha.example.com"


@pytest.mark.asyncio
async def test_missing_auth_sessions_stays_a_hard_500(client, db_engine):
    """auth_sessions is required. A valid password must not become HTTP 200 when the insert cannot land."""
    from app.http_errors import SAFE_500

    ac, _seed = client
    wrong_password = await ac.post(
        "/api/v1/auth/login",
        json={
            "email": "cashier@alpha.example.com",
            "password": "WrongPass123!",
            "tenant_id": "alpha",
            "totp_code": None,
        },
    )
    assert wrong_password.status_code == 401, wrong_password.text

    async with db_engine.begin() as conn:
        await conn.execute(text("DROP TABLE auth_sessions"))
    schema_compat.clear_column_cache()

    still_wrong = await ac.post(
        "/api/v1/auth/login",
        json={
            "email": "cashier@alpha.example.com",
            "password": "WrongPass123!",
            "tenant_id": "alpha",
            "totp_code": None,
        },
    )
    assert still_wrong.status_code == 401, still_wrong.text
    assert still_wrong.json()["detail"] == "Invalid credentials"

    failed = await ac.post(
        "/api/v1/auth/login",
        json={
            "email": "cashier@alpha.example.com",
            "password": "SecurePass123!",
            "tenant_id": "alpha",
            "totp_code": None,
        },
    )
    assert failed.status_code == 500, failed.text
    assert failed.json()["detail"] == SAFE_500
    body = failed.text.lower()
    assert "access_token" not in body
    assert "traceback" not in body
    assert "auth_sessions" not in body
    assert "select " not in body
    assert "securepass" not in body
