"""Stage 151 A1 — platform at-risk tenants CSV export."""

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

ROOT = Path(__file__).resolve().parents[2]


async def _platform_headers(ac, db_engine, email="staff-151a@ribdigi.example.com"):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as db:
        await ensure_platform_tenant(db)
        secret = pyotp.random_base32()
        user = m.User(
            tenant_id=PLATFORM_TENANT_ID,
            email=email,
            full_name="Staff 151 AtRisk",
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
    return {"Authorization": f"Bearer {token}", "X-Tenant-ID": "ribdigi-platform"}


@pytest.mark.asyncio
async def test_platform_at_risk_export_csv(client, db_engine):
    ac, _seed = client
    headers = await _platform_headers(ac, db_engine)
    exported = await ac.get(
        "/api/v1/platform/tenants/at-risk/export?within_days=14",
        headers=headers,
    )
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    text = exported.text
    header = text.splitlines()[0]
    assert "tenant_id" in header and "company_name" in header and "risk_ends_at" in header
    assert "days_remaining" in header and "within_days" in header


def test_platform_at_risk_export_ui_a1():
    page = (ROOT / "frontend/app/platform/tenants/page.tsx").read_text(encoding="utf-8")
    assert "Stage 151" in page
    assert "/platform/tenants/at-risk/export" in page
    assert "Export at-risk CSV" in page
    assert "at-risk-queue" in page
