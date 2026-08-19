"""Stage 80 P1 — Platform owner dashboard charts (real aggregates, no fake MRR)."""

from __future__ import annotations

import pyotp
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app import models as m
from app import totp as totp_svc
from app.platform import ensure_platform_tenant
from app.platform_const import PLATFORM_SUPER_ADMIN, PLATFORM_TENANT_ID
from app.rbac import permissions_for_role
from app.security import hash_password
from tests.conftest import auth_headers


async def _seed_platform_admin(db: AsyncSession) -> tuple[m.User, str]:
    await ensure_platform_tenant(db)
    secret = pyotp.random_base32()
    user = m.User(
        tenant_id=PLATFORM_TENANT_ID,
        email="charts-ops@ribdigi.example.com",
        full_name="Charts Ops",
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
            "email": "charts-ops@ribdigi.example.com",
            "password": "SecurePass123!",
            "tenant_id": "ribdigi-platform",
            "totp_code": code,
        },
    )
    assert login.status_code == 200, login.text
    data = login.json()["data"]
    token = data["access_token"]
    return {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": PLATFORM_TENANT_ID,
    }


@pytest.mark.asyncio
async def test_platform_dashboard_includes_charts(client, db_engine):
    ac, _seeded = client
    headers = await _platform_headers(ac, db_engine)
    r = await ac.get("/api/v1/platform/dashboard", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["billing"]["deferred"] is True
    assert data["billing"]["mrr"] is None
    assert "tenant_growth" in data and "series" in data["tenant_growth"]
    assert "tenant_status" in data and "slices" in data["tenant_status"]
    assert "plan_distribution" in data
    assert "industry_distribution" in data
    assert "user_growth" in data and "series" in data["user_growth"]
    assert len(data["tenant_growth"]["series"]) >= 1


@pytest.mark.asyncio
async def test_platform_dashboard_chart_subroutes(client, db_engine):
    ac, _seeded = client
    headers = await _platform_headers(ac, db_engine)
    for path in (
        "/api/v1/platform/dashboard/summary",
        "/api/v1/platform/dashboard/tenant-growth",
        "/api/v1/platform/dashboard/tenant-status",
        "/api/v1/platform/dashboard/industry-distribution",
        "/api/v1/platform/dashboard/plan-distribution",
        "/api/v1/platform/dashboard/user-growth",
    ):
        r = await ac.get(path, headers=headers)
        assert r.status_code == 200, path


@pytest.mark.asyncio
async def test_tenant_admin_cannot_access_platform_charts(client):
    ac, _seeded = client
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    r = await ac.get("/api/v1/platform/dashboard/tenant-growth", headers=admin)
    assert r.status_code == 403
