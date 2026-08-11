"""Stage 87 Y1 — House ops surface polish."""

from __future__ import annotations

from pathlib import Path

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

ROOT = Path(__file__).resolve().parents[2]


async def _platform_headers(ac, db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as db:
        await ensure_platform_tenant(db)
        secret = pyotp.random_base32()
        user = m.User(
            tenant_id=PLATFORM_TENANT_ID,
            email="ops-y1@ribdigi.example.com",
            full_name="Ops Y1",
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
    code = pyotp.TOTP(secret).now()
    login = await ac.post(
        "/api/v1/auth/login",
        json={
            "email": "ops-y1@ribdigi.example.com",
            "password": "SecurePass123!",
            "tenant_id": "ribdigi-platform",
            "totp_code": code,
        },
    )
    assert login.status_code == 200, login.text
    token = login.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}", "X-Tenant-ID": PLATFORM_TENANT_ID}


@pytest.mark.asyncio
async def test_platform_health_has_checks(client, db_engine):
    ac, _seed = client
    headers = await _platform_headers(ac, db_engine)
    r = await ac.get("/api/v1/platform/health", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert "checks" in data
    assert "database" in data["checks"]


@pytest.mark.asyncio
async def test_tenant_detail_exposes_last_activity_and_notes(client, db_engine):
    ac, seed = client
    headers = await _platform_headers(ac, db_engine)
    tid = seed["t1"].id
    r = await ac.get(f"/api/v1/platform/tenants/{tid}", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert "last_activity_at" in data
    assert "platform_notes" in data

    patch = await ac.patch(
        f"/api/v1/platform/tenants/{tid}/notes",
        headers=headers,
        json={"platform_notes": "House follow-up"},
    )
    assert patch.status_code == 200, patch.text
    assert patch.json()["data"]["platform_notes"] == "House follow-up"


@pytest.mark.asyncio
async def test_tenant_cannot_set_platform_notes(client, db_engine):
    ac, seed = client
    mgr = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    r = await ac.patch(
        f"/api/v1/platform/tenants/{seed['t1'].id}/notes",
        headers=mgr,
        json={"platform_notes": "nope"},
    )
    assert r.status_code == 403


def test_house_ops_ui_surfaces():
    health = (ROOT / "frontend/app/platform/health/page.tsx").read_text(encoding="utf-8")
    assert "checks" in health or "database" in health
    detail = (ROOT / "frontend/app/platform/tenants/[id]/page.tsx").read_text(encoding="utf-8")
    assert "last_activity_at" in detail
    assert "platform_notes" in detail or "operator notes" in detail.lower()
    settings = (ROOT / "frontend/app/platform/settings/page.tsx").read_text(encoding="utf-8")
    assert "Company" in settings or "company profile" in settings.lower()
