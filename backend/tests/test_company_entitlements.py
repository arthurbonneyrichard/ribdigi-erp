"""Plan-synced company entitlement enforcement tests."""

from __future__ import annotations

import pyotp
import pytest

from app import models as m
from app import store_entitlements as store_ent_svc
from tests.conftest import auth_headers


async def _super_headers(ac, seed) -> dict:
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    headers = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    headers["X-Workspace-Kind"] = "tenant"
    return headers


async def _platform_headers(ac, db_engine, email="ops-companies@ribdigi.example.com") -> dict:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from app import totp as totp_svc
    from app.platform import ensure_platform_tenant
    from app.platform_const import PLATFORM_SUPER_ADMIN, PLATFORM_TENANT_ID, PLATFORM_TENANT_SLUG
    from app.rbac import permissions_for_role
    from app.security import hash_password

    session_factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as db:
        await ensure_platform_tenant(db)
        secret = pyotp.random_base32()
        db.add(
            m.User(
                tenant_id=PLATFORM_TENANT_ID,
                email=email,
                full_name="Platform Ops Companies",
                password_hash=hash_password("SecurePass123!"),
                role=PLATFORM_SUPER_ADMIN,
                email_verified=True,
                permissions=permissions_for_role(PLATFORM_SUPER_ADMIN),
                totp_enabled=True,
                totp_secret_enc=totp_svc.encrypt_secret(secret),
                totp_confirmed_at=__import__("datetime").datetime.utcnow(),
            )
        )
        await db.commit()

    code = pyotp.TOTP(secret).now()
    login = await ac.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": "SecurePass123!",
            "tenant_id": PLATFORM_TENANT_SLUG,
            "totp_code": code,
        },
    )
    assert login.status_code == 200, login.text
    return {
        "Authorization": f"Bearer {login.json()['data']['access_token']}",
        "X-Tenant-ID": PLATFORM_TENANT_ID,
    }


@pytest.mark.asyncio
async def test_plan_catalog_company_soft_limits():
    assert store_ent_svc.plan_default_max_companies("trial") == 1
    assert store_ent_svc.plan_default_max_companies("starter") == 1
    assert store_ent_svc.plan_default_max_companies("growth") == 3
    assert store_ent_svc.plan_default_max_companies("enterprise") == store_ent_svc.UNLIMITED


@pytest.mark.asyncio
async def test_plan_upgrade_syncs_max_companies_when_no_override(client, db_session):
    ac, seed = client
    seed["t1"].max_companies = 1
    seed["t1"].max_companies_override = None
    seed["t1"].plan_code = "starter"
    await db_session.commit()

    info = store_ent_svc.apply_plan_company_defaults(seed["t1"], "growth")
    assert info["synced"] is True
    assert seed["t1"].max_companies == 3


@pytest.mark.asyncio
async def test_plan_sync_skipped_when_company_override_set(client, db_session):
    ac, seed = client
    seed["t1"].max_companies = 1
    seed["t1"].max_companies_override = 5
    await db_session.commit()

    info = store_ent_svc.apply_plan_company_defaults(seed["t1"], "growth")
    assert info["synced"] is False
    assert info["reason"] == "override_set"
    assert seed["t1"].max_companies == 1


@pytest.mark.asyncio
async def test_platform_override_increases_effective_company_limit(client, db_session, db_engine):
    ac, seed = client
    seed["t1"].max_companies = 1
    seed["t1"].max_companies_override = None
    await db_session.commit()

    headers = await _platform_headers(ac, db_engine)
    r = await ac.patch(
        f"/api/v1/platform/tenants/{seed['t1'].id}/company-entitlement",
        headers=headers,
        json={"max_companies_override": 4},
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["company_entitlement"]["effective"] == 4

    await db_session.refresh(seed["t1"])
    assert store_ent_svc.effective_tenant_company_limit(seed["t1"]) == 4


@pytest.mark.asyncio
async def test_downgrade_does_not_delete_companies(client, db_session):
    ac, seed = client
    seed["t1"].max_companies = 5
    seed["t1"].max_companies_override = None
    await db_session.commit()

    headers = await _super_headers(ac, seed)
    for i in range(2):
        r = await ac.post(
            "/api/v1/companies",
            headers=headers,
            json={"name": f"Keep Co {i}", "code": f"KC{i}", "industry": "retail"},
        )
        assert r.status_code in (200, 201), r.text

    seed["t1"].max_companies = 1
    seed["t1"].max_companies_override = None
    await db_session.commit()

    count = await store_ent_svc.count_active_companies(db_session, seed["t1"].id)
    assert count == 3  # default + 2 created

    blocked = await ac.post(
        "/api/v1/companies",
        headers=headers,
        json={"name": "After Downgrade", "code": "AFTER", "industry": "retail"},
    )
    assert blocked.status_code == 403
    assert blocked.json()["detail"]["code"] == "COMPANY_LIMIT_REACHED"

    ent = await store_ent_svc.get_tenant_company_entitlement(db_session, seed["t1"])
    assert ent["over_entitlement"] is True


@pytest.mark.asyncio
async def test_company_create_blocked_at_effective_limit(client, db_session):
    ac, seed = client
    seed["t1"].max_companies = 3
    seed["t1"].max_companies_override = None
    await db_session.commit()

    headers = await _super_headers(ac, seed)
    for i in range(2):
        r = await ac.post(
            "/api/v1/companies",
            headers=headers,
            json={"name": f"Extra Co {i}", "code": f"EX{i}", "industry": "retail"},
        )
        assert r.status_code in (200, 201), r.text

    r = await ac.post(
        "/api/v1/companies",
        headers=headers,
        json={"name": "Over Limit", "code": "OVER", "industry": "retail"},
    )
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "COMPANY_LIMIT_REACHED"
