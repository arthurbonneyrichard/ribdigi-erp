"""Grant/revoke app user access to the software-owner dashboard."""

from __future__ import annotations

import pyotp
import pytest
from sqlalchemy import select

from app import models as m
from app.rbac import permissions_for_role
from app.security import hash_password
from tests.conftest import auth_headers


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_grant_and_revoke_app_user_dashboard(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)

    app_user = m.User(
        tenant_id=seed["t1"].id,
        email="ops.app@alpha.example.com",
        full_name="Ops App User",
        password_hash=hash_password("SecurePass123!"),
        role="company_admin",
        email_verified=True,
        permissions=permissions_for_role("company_admin"),
        totp_enabled=False,
    )
    db_session.add(app_user)
    await db_session.commit()
    await db_session.refresh(app_user)

    listed = await ac.get("/api/v1/platform/app-users", headers=headers)
    assert listed.status_code == 200, listed.text
    emails = {u["email"] for u in listed.json()["data"]}
    assert "ops.app@alpha.example.com" in emails
    assert "super@alpha.example.com" not in emails

    # Tenant company_admin cannot hit platform grant
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    # company_admin may require 2FA enrollment — accept 403 either way
    denied = await ac.post(
        "/api/v1/platform/staff/grant",
        headers=admin,
        json={"user_id": app_user.id, "role": "platform_support"},
    )
    assert denied.status_code == 403, denied.text

    granted = await ac.post(
        "/api/v1/platform/staff/grant",
        headers=headers,
        json={"user_id": app_user.id, "role": "platform_support"},
    )
    assert granted.status_code == 200, granted.text
    assert granted.json()["data"]["role"] == "platform_support"

    staff = await ac.get("/api/v1/platform/staff", headers=headers)
    assert "ops.app@alpha.example.com" in {u["email"] for u in staff.json()["data"]}

    remaining = await ac.get("/api/v1/platform/app-users", headers=headers)
    assert "ops.app@alpha.example.com" not in {u["email"] for u in remaining.json()["data"]}

    # Granted user can read platform tenants (support role)
    # May need 2FA for platform_support? support is not in ENFORCED_ROLES typically
    support_headers = await auth_headers(
        ac, email="ops.app@alpha.example.com", tenant_slug="alpha"
    )
    ok = await ac.get("/api/v1/tenants", headers=support_headers)
    assert ok.status_code == 200, ok.text

    revoked = await ac.post(
        f"/api/v1/platform/staff/{app_user.id}/revoke",
        headers=headers,
        json={"fallback_role": "cashier"},
    )
    assert revoked.status_code == 200, revoked.text
    assert revoked.json()["data"]["role"] == "cashier"
    assert "platform_tenants" not in (revoked.json()["data"].get("permissions") or {})

    # After revoke, platform APIs denied
    after = await auth_headers(ac, email="ops.app@alpha.example.com", tenant_slug="alpha")
    blocked = await ac.get("/api/v1/tenants", headers=after)
    assert blocked.status_code == 403, blocked.text


@pytest.mark.asyncio
async def test_grant_isolation_cross_tenant(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)
    beta_user = m.User(
        tenant_id=seed["t2"].id,
        email="other@beta.example.com",
        full_name="Beta User",
        password_hash=hash_password("SecurePass123!"),
        role="cashier",
        email_verified=True,
        permissions=permissions_for_role("cashier"),
        totp_enabled=False,
    )
    db_session.add(beta_user)
    await db_session.commit()
    await db_session.refresh(beta_user)

    steal = await ac.post(
        "/api/v1/platform/staff/grant",
        headers=headers,
        json={"user_id": beta_user.id, "role": "platform_finance"},
    )
    assert steal.status_code == 404, steal.text
