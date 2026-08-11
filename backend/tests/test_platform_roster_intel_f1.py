"""Stage 89 F1 — Roster filters + dashboard at-risk KPIs."""

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

ROOT = Path(__file__).resolve().parents[2]


async def _platform_headers(ac, db_engine, email="intel-f1@ribdigi.example.com"):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as db:
        await ensure_platform_tenant(db)
        secret = pyotp.random_base32()
        user = m.User(
            tenant_id=PLATFORM_TENANT_ID,
            email=email,
            full_name="Intel F1",
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
async def test_tenant_list_plan_and_industry_filters(client, db_engine):
    ac, seed = client
    headers = await _platform_headers(ac, db_engine)
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as db:
        t = await db.get(m.Tenant, seed["t1"].id)
        t.plan_code = "starter"
        t.industry = "pharmacy"
        await db.commit()

    r = await ac.get(
        "/api/v1/platform/tenants?plan_code=starter&industry=pharmacy",
        headers=headers,
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["total"] >= 1
    assert all(i.get("plan_code") == "starter" for i in data["items"])
    assert all((i.get("industry") or "").lower() == "pharmacy" for i in data["items"])
    assert data["filters"]["plan_code"] == "starter"


@pytest.mark.asyncio
async def test_dashboard_exposes_grace_and_at_risk(client, db_engine):
    ac, seed = client
    headers = await _platform_headers(ac, db_engine, email="intel-f1b@ribdigi.example.com")
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as db:
        t = await db.get(m.Tenant, seed["t1"].id)
        t.status = "trial"
        t.trial_ends_at = datetime.utcnow() + timedelta(days=2)
        await db.commit()

    r = await ac.get("/api/v1/platform/dashboard", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert "grace_tenants" in data
    assert "at_risk_count" in data
    assert data["at_risk_count"] >= 1


def test_ui_has_filters_and_dashboard_risk_cards():
    tenants = (ROOT / "frontend/app/platform/tenants/page.tsx").read_text(encoding="utf-8")
    assert "plan_code" in tenants and "industry" in tenants
    dash = (ROOT / "frontend/app/platform/dashboard/page.tsx").read_text(encoding="utf-8")
    assert "grace_tenants" in dash
    assert "at_risk_count" in dash
    assert "/platform/tenants" in dash
