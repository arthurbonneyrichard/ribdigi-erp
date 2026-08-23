"""Plan-synced user entitlement enforcement tests."""

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


async def _platform_headers(ac, db_engine, email="ops-users@ribdigi.example.com") -> dict:
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
                full_name="Platform Ops Users",
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


def _user_payload(i: int) -> dict:
    return {
        "email": f"hire{i}@alpha.example.com",
        "full_name": f"Hire User {i}",
        "password": "SecurePass123!",
        "role": "cashier",
    }


@pytest.mark.asyncio
async def test_plan_catalog_user_soft_limits():
    assert store_ent_svc.plan_default_max_users("trial") == 5
    assert store_ent_svc.plan_default_max_users("starter") == 15
    assert store_ent_svc.plan_default_max_users("growth") == 50
    assert store_ent_svc.plan_default_max_users("enterprise") == store_ent_svc.UNLIMITED


@pytest.mark.asyncio
async def test_plan_upgrade_syncs_max_users_when_no_override(client, db_session):
    ac, seed = client
    seed["t1"].max_users = 5
    seed["t1"].max_users_override = None
    seed["t1"].plan_code = "starter"
    await db_session.commit()

    info = store_ent_svc.apply_plan_user_defaults(seed["t1"], "growth")
    assert info["synced"] is True
    assert seed["t1"].max_users == 50


@pytest.mark.asyncio
async def test_plan_sync_skipped_when_user_override_set(client, db_session):
    ac, seed = client
    seed["t1"].max_users = 5
    seed["t1"].max_users_override = 40
    await db_session.commit()

    info = store_ent_svc.apply_plan_user_defaults(seed["t1"], "growth")
    assert info["synced"] is False
    assert info["reason"] == "override_set"
    assert seed["t1"].max_users == 5


@pytest.mark.asyncio
async def test_platform_override_increases_effective_user_limit(client, db_session, db_engine):
    ac, seed = client
    seed["t1"].max_users = 5
    seed["t1"].max_users_override = None
    await db_session.commit()

    headers = await _platform_headers(ac, db_engine)
    r = await ac.patch(
        f"/api/v1/platform/tenants/{seed['t1'].id}/user-entitlement",
        headers=headers,
        json={"max_users_override": 12},
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["user_entitlement"]["effective"] == 12

    await db_session.refresh(seed["t1"])
    assert store_ent_svc.effective_tenant_user_limit(seed["t1"]) == 12


@pytest.mark.asyncio
async def test_downgrade_does_not_delete_users(client, db_session):
    ac, seed = client
    # Seed has 4 active users; raise then lower limit without deleting.
    seed["t1"].max_users = 10
    seed["t1"].max_users_override = None
    await db_session.commit()

    headers = await _super_headers(ac, seed)
    created = await ac.post("/api/v1/users", headers=headers, json=_user_payload(1))
    assert created.status_code in (200, 201), created.text

    seed["t1"].max_users = 4
    seed["t1"].max_users_override = None
    await db_session.commit()

    count = await store_ent_svc.count_active_users(db_session, seed["t1"].id)
    assert count == 5  # 4 seed + 1 created; none deleted

    blocked = await ac.post("/api/v1/users", headers=headers, json=_user_payload(2))
    assert blocked.status_code == 403
    assert blocked.json()["detail"]["code"] == "USER_LIMIT_REACHED"

    ent = await store_ent_svc.get_tenant_user_entitlement(db_session, seed["t1"])
    assert ent["over_entitlement"] is True


@pytest.mark.asyncio
async def test_user_create_blocked_at_effective_limit(client, db_session):
    ac, seed = client
    seed["t1"].max_users = 4
    seed["t1"].max_users_override = None
    await db_session.commit()

    headers = await _super_headers(ac, seed)
    r = await ac.post("/api/v1/users", headers=headers, json=_user_payload(9))
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "USER_LIMIT_REACHED"


@pytest.mark.asyncio
async def test_user_reactivation_blocked_when_at_limit(client, db_session):
    ac, seed = client
    seed["t1"].max_users = 10
    seed["t1"].max_users_override = None
    await db_session.commit()

    headers = await _super_headers(ac, seed)
    created = await ac.post("/api/v1/users", headers=headers, json=_user_payload(20))
    assert created.status_code in (200, 201), created.text
    user_id = created.json()["data"]["id"]
    if isinstance(created.json()["data"].get("user"), dict):
        user_id = created.json()["data"]["user"].get("id") or user_id

    deact = await ac.patch(
        f"/api/v1/users/{user_id}",
        headers=headers,
        json={"is_active": False},
    )
    assert deact.status_code == 200, deact.text

    # Fill back to limit with max_users == active count.
    used = await store_ent_svc.count_active_users(db_session, seed["t1"].id)
    seed["t1"].max_users = used
    seed["t1"].max_users_override = None
    await db_session.commit()

    blocked = await ac.patch(
        f"/api/v1/users/{user_id}",
        headers=headers,
        json={"is_active": True},
    )
    assert blocked.status_code == 403
    assert blocked.json()["detail"]["code"] == "USER_LIMIT_REACHED"
