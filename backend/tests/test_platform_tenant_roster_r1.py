"""Stage 88 R1 — Tenant roster export + at-risk queue."""

from __future__ import annotations

from datetime import datetime, timedelta
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


async def _platform_headers(ac, db_engine, email="roster-r1@ribdigi.example.com"):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as db:
        await ensure_platform_tenant(db)
        secret = pyotp.random_base32()
        user = m.User(
            tenant_id=PLATFORM_TENANT_ID,
            email=email,
            full_name="Roster R1",
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
            "email": email,
            "password": "SecurePass123!",
            "tenant_id": "ribdigi-platform",
            "totp_code": code,
        },
    )
    assert login.status_code == 200, login.text
    token = login.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}", "X-Tenant-ID": PLATFORM_TENANT_ID}


@pytest.mark.asyncio
async def test_tenants_export_csv(client, db_engine):
    ac, _seed = client
    headers = await _platform_headers(ac, db_engine)
    r = await ac.get("/api/v1/platform/tenants/export?format=csv", headers=headers)
    assert r.status_code == 200, r.text
    assert "text/csv" in r.headers.get("content-type", "")
    assert "platform-tenants.csv" in r.headers.get("content-disposition", "")
    assert "company_name" in r.text


@pytest.mark.asyncio
async def test_tenants_at_risk_queue(client, db_engine):
    ac, seed = client
    headers = await _platform_headers(ac, db_engine)
    # Ensure seed tenant is trial ending soon
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as db:
        t = await db.get(m.Tenant, seed["t1"].id)
        t.status = "trial"
        t.trial_ends_at = datetime.utcnow() + timedelta(days=3)
        t.grace_ends_at = None
        await db.commit()

    r = await ac.get("/api/v1/platform/tenants/at-risk?within_days=14", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["within_days"] == 14
    assert data["total"] >= 1
    ids = {i["id"] for i in data["items"]}
    assert seed["t1"].id in ids


@pytest.mark.asyncio
async def test_tenant_cannot_export_roster(client):
    ac, _seed = client
    mgr = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    r = await ac.get("/api/v1/platform/tenants/export", headers=mgr)
    assert r.status_code == 403


def test_tenants_ui_has_export_and_at_risk():
    page = (ROOT / "frontend/app/platform/tenants/page.tsx").read_text(encoding="utf-8")
    assert "/platform/tenants/export" in page
    assert "Export CSV" in page and "Export PDF" in page
    assert "/platform/tenants/at-risk" in page
    assert "At-risk" in page
