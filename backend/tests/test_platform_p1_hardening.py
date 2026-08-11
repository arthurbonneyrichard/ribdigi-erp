"""ADR-137 P1: platform hardening, users, plan metadata, billing honesty."""

from __future__ import annotations

import pyotp
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app import models as m
from app import totp as totp_svc
from app.platform import ensure_platform_tenant
from app.platform_const import PLATFORM_SUPER_ADMIN, PLATFORM_TENANT_ID, PLATFORM_TENANT_SLUG
from app.rbac import permissions_for_role
from app.security import hash_password
from tests.conftest import auth_headers


async def _seed_platform_admin(db: AsyncSession) -> tuple[m.User, str]:
    await ensure_platform_tenant(db)
    secret = pyotp.random_base32()
    user = m.User(
        tenant_id=PLATFORM_TENANT_ID,
        email="ops@ribdigi.example.com",
        full_name="Platform Ops",
        password_hash=hash_password("SecurePass123!"),
        role=PLATFORM_SUPER_ADMIN,
        email_verified=True,
        permissions=permissions_for_role(PLATFORM_SUPER_ADMIN),
        totp_enabled=True,
        totp_secret_enc=totp_svc.encrypt_secret(secret),
        totp_confirmed_at=__import__("datetime").datetime.utcnow(),
    )
    db.add(user)
    await db.commit()
    return user, secret


async def _platform_headers(ac, db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as db:
        _user, secret = await _seed_platform_admin(db)
    code = pyotp.TOTP(secret).now()
    login = await ac.post(
        "/api/v1/auth/login",
        json={
            "email": "ops@ribdigi.example.com",
            "password": "SecurePass123!",
            "tenant_id": PLATFORM_TENANT_SLUG,
            "totp_code": code,
        },
    )
    assert login.status_code == 200, login.text
    token = login.json()["data"]["access_token"]
    return {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": PLATFORM_TENANT_ID,
    }, login.json()["data"]


@pytest.mark.asyncio
async def test_legacy_super_admin_cannot_suspend_platform_tenant(client, db_engine):
    ac, seeded = client
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as db:
        await ensure_platform_tenant(db)
        await db.commit()

    import pyotp as _pyotp

    secret = seeded["super_totp_secret"]
    code = _pyotp.TOTP(secret).now()
    headers = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )

    listed = await ac.get("/api/v1/tenants", headers=headers)
    assert listed.status_code == 410
    assert listed.json()["detail"]["code"] == "PLATFORM_API_REQUIRED"

    bad = await ac.post(f"/api/v1/tenants/{PLATFORM_TENANT_ID}/suspend", headers=headers)
    assert bad.status_code == 410
    assert bad.json()["detail"]["code"] == "PLATFORM_API_REQUIRED"


@pytest.mark.asyncio
async def test_platform_suspend_revokes_customer_sessions(client, db_engine):
    ac, seeded = client
    headers, _ = await _platform_headers(ac, db_engine)

    # Customer cashier logs in
    cash_h = await auth_headers(ac, email="cashier@beta.example.com", tenant_slug="beta")
    ok = await ac.get("/api/v1/me", headers=cash_h)
    assert ok.status_code == 200

    tid = seeded["t2"].id
    sus = await ac.post(f"/api/v1/platform/tenants/{tid}/suspend", headers=headers)
    assert sus.status_code == 200, sus.text
    assert sus.json()["data"]["status"] == "suspended"

    blocked = await ac.get("/api/v1/me", headers=cash_h)
    assert blocked.status_code in (401, 403)

    act = await ac.post(f"/api/v1/platform/tenants/{tid}/activate", headers=headers)
    assert act.status_code == 200


@pytest.mark.asyncio
async def test_platform_users_and_plan_and_billing(client, db_engine):
    ac, seeded = client
    headers, data = await _platform_headers(ac, db_engine)
    assert data["principal"] == "platform"

    users = await ac.get("/api/v1/platform/users", headers=headers)
    assert users.status_code == 200
    assert any(u["email"] == "ops@ribdigi.example.com" for u in users.json()["data"])

    created = await ac.post(
        "/api/v1/platform/users",
        headers=headers,
        json={
            "email": "ops2@ribdigi.example.com",
            "full_name": "Ops Two",
            "password": "SecurePass123!",
            "role": "platform_admin",
        },
    )
    assert created.status_code == 200, created.text
    assert created.json()["data"]["role"] == "platform_admin"
    assert created.json()["data"]["email_verified"] is True

    # Tenant ERP users API still blocked for platform principal
    erp_users = await ac.get("/api/v1/users", headers=headers)
    assert erp_users.status_code == 403
    detail = erp_users.json().get("detail")
    assert isinstance(detail, dict)
    assert detail.get("code") == "PLATFORM_USE_PLATFORM_API"

    # Onboarding (current_claims-only) also blocked by allowlist
    onboarding = await ac.get("/api/v1/onboarding/checklist", headers=headers)
    assert onboarding.status_code == 403

    tid = seeded["t1"].id
    plan = await ac.patch(
        f"/api/v1/platform/tenants/{tid}/plan",
        headers=headers,
        json={"plan_code": "growth"},
    )
    assert plan.status_code == 200, plan.text
    assert plan.json()["data"]["plan_code"] == "growth"

    billing = await ac.get("/api/v1/platform/billing", headers=headers)
    assert billing.status_code == 200
    body = billing.json()["data"]
    assert body["deferred"] is True
    assert body["mrr"] is None
    assert body["checkout_enabled"] is False

    settings = await ac.get("/api/v1/platform/settings", headers=headers)
    assert settings.status_code == 200
    assert settings.json()["data"]["slug"] == PLATFORM_TENANT_SLUG

    patched = await ac.patch(
        "/api/v1/platform/settings",
        headers=headers,
        json={"inactivity_timeout_minutes": 45, "support_email": "house@ribdigi.example.com"},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["data"]["inactivity_timeout_minutes"] == 45
    assert patched.json()["data"]["support_email"] == "house@ribdigi.example.com"


def test_normalize_permissions_rejects_platform_modules_for_customer_roles():
    from app.rbac import normalize_permissions_map

    with pytest.raises(ValueError, match="Platform module"):
        normalize_permissions_map(
            {"platform_dashboard": ["read"], "dashboard": ["read"]},
            allow_wildcard=False,
            allow_platform_modules=False,
        )
    ok = normalize_permissions_map(
        {"platform_dashboard": ["read"]},
        allow_wildcard=False,
        allow_platform_modules=True,
    )
    assert "platform_dashboard" in ok
