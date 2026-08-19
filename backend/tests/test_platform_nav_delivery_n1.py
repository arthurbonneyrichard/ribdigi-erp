"""Stage 91 N1 — Dashboard→roster deep-links + tenant last delivery context."""

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


async def _platform_headers(ac, db_engine, email="nav-n1@ribdigi.example.com"):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as db:
        await ensure_platform_tenant(db)
        secret = pyotp.random_base32()
        user = m.User(
            tenant_id=PLATFORM_TENANT_ID,
            email=email,
            full_name="Nav N1",
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
async def test_tenant_detail_includes_last_house_email_delivery(client, db_engine):
    ac, seed = client
    headers = await _platform_headers(ac, db_engine)
    tid = seed["t1"].id
    r = await ac.post(
        f"/api/v1/platform/tenants/{tid}/admin/password-reset-email",
        headers=headers,
        json={},
    )
    assert r.status_code == 200, r.text

    detail = await ac.get(f"/api/v1/platform/tenants/{tid}", headers=headers)
    assert detail.status_code == 200, detail.text
    delivery = detail.json()["data"].get("last_house_email_delivery")
    assert delivery is not None
    assert delivery.get("recipient")
    assert "sent" in delivery and "mode" in delivery
    assert delivery.get("fabricated_success") is False


def test_dashboard_and_tenants_deep_link_wiring():
    dash = (ROOT / "frontend/app/platform/dashboard/page.tsx").read_text(encoding="utf-8")
    assert "/platform/tenants?status=grace" in dash
    assert "/platform/tenants?status=suspended" in dash
    assert "focus=at-risk" in dash
    tenants = (ROOT / "frontend/app/platform/tenants/page.tsx").read_text(encoding="utf-8")
    assert "useSearchParams" in tenants
    assert "searchParams.get('status')" in tenants or 'searchParams.get("status")' in tenants
    assert "at-risk-queue" in tenants
    detail = (ROOT / "frontend/app/platform/tenants/[id]/page.tsx").read_text(encoding="utf-8")
    assert "last_house_email_delivery" in detail
