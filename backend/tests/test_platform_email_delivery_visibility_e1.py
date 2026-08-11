"""Stage 90 E1 — House email delivery visibility."""

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


async def _platform_headers(ac, db_engine, email="delivery-e1@ribdigi.example.com"):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as db:
        await ensure_platform_tenant(db)
        secret = pyotp.random_base32()
        user = m.User(
            tenant_id=PLATFORM_TENANT_ID,
            email=email,
            full_name="Delivery E1",
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
async def test_assist_email_records_delivery_audit(client, db_engine):
    ac, seed = client
    headers = await _platform_headers(ac, db_engine)
    tid = seed["t1"].id
    r = await ac.post(
        f"/api/v1/platform/tenants/{tid}/admin/password-reset-email",
        headers=headers,
        json={},
    )
    assert r.status_code == 200, r.text
    assert "email_delivery" in r.json()["data"]

    listed = await ac.get(
        "/api/v1/platform/audit?delivery_only=true",
        headers=headers,
    )
    assert listed.status_code == 200, listed.text
    items = listed.json()["data"]["items"]
    assert items
    assert all(i.get("action") == "platform.email.delivery" for i in items)
    details = items[0].get("details") or {}
    assert "sent" in details and "mode" in details
    assert details.get("fabricated_success") is False
    assert details.get("recipient")


def test_audit_ui_surfaces_delivery_details():
    page = (ROOT / "frontend/app/platform/audit/page.tsx").read_text(encoding="utf-8")
    assert "delivery_only" in page or "Delivery only" in page
    assert "platform.email.delivery" in page
    assert "details" in page
