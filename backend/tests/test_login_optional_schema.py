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
