"""Stage 92 B1 — Investigation export + evidence download workflow."""

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


async def _platform_headers(ac, db_engine, email="workflow-b1@ribdigi.example.com"):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as db:
        await ensure_platform_tenant(db)
        secret = pyotp.random_base32()
        user = m.User(
            tenant_id=PLATFORM_TENANT_ID,
            email=email,
            full_name="Workflow B1",
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
async def test_audit_export_delivery_only_and_evidence(client, db_engine):
    ac, seed = client
    headers = await _platform_headers(ac, db_engine)
    tid = seed["t1"].id
    r = await ac.post(
        f"/api/v1/platform/tenants/{tid}/admin/password-reset-email",
        headers=headers,
        json={},
    )
    assert r.status_code == 200, r.text

    exported = await ac.get(
        "/api/v1/platform/audit/export?delivery_only=true&format=csv",
        headers=headers,
    )
    assert exported.status_code == 200, exported.text
    assert "platform.email.delivery" in exported.text
    assert "text/csv" in exported.headers.get("content-type", "")

    evidence = await ac.get("/api/v1/platform/evidence", headers=headers)
    assert evidence.status_code == 200, evidence.text
    assert evidence.json()["data"].get("packaging_only") is True
    assert evidence.json()["data"]["honesty_flags"].get("go_live_claimed") is False


def test_audit_and_health_ui_export_wiring():
    audit = (ROOT / "frontend/app/platform/audit/page.tsx").read_text(encoding="utf-8")
    assert "delivery_only" in audit
    assert "activityDefaultFromDate" in audit or "setDate(d.getDate() - 7)" in audit
    health = (ROOT / "frontend/app/platform/health/page.tsx").read_text(encoding="utf-8")
    assert "Download evidence JSON" in health
    assert "/platform/evidence" in health
