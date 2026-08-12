"""Stage 150 R1 — platform subscriptions roster CSV export."""

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


async def _platform_headers(ac, db_engine, email="staff-150r@ribdigi.example.com"):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as db:
        await ensure_platform_tenant(db)
        secret = pyotp.random_base32()
        user = m.User(
            tenant_id=PLATFORM_TENANT_ID,
            email=email,
            full_name="Staff 150 Roster",
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
async def test_platform_subscriptions_export_csv(client, db_engine):
    ac, seed = client
    headers = await _platform_headers(ac, db_engine)
    exported = await ac.get("/api/v1/platform/subscriptions/export", headers=headers)
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    text = exported.text
    header = text.splitlines()[0]
    assert "tenant_id" in header and "plan_code" in header and "deferred_billing" in header
    assert seed["t1"].slug in text or seed["t1"].company_name in text
    assert "subscriptions_live" in header
    # Honesty: empty MRR cell column present; no fabricated dollar MRR claim
    assert "mrr" in header


def test_platform_subscriptions_export_ui_r1():
    page = (ROOT / "frontend/app/platform/billing/page.tsx").read_text(encoding="utf-8")
    assert "Stage 150" in page
    assert "/platform/subscriptions/export" in page
    assert "Export subscriptions CSV" in page
