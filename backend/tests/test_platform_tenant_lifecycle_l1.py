"""Stage 88 L1 — Tenant lifecycle controls."""

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


async def _platform_headers(ac, db_engine, email="lifecycle-l1@ribdigi.example.com"):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as db:
        await ensure_platform_tenant(db)
        secret = pyotp.random_base32()
        user = m.User(
            tenant_id=PLATFORM_TENANT_ID,
            email=email,
            full_name="Lifecycle L1",
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
async def test_extend_trial_and_suspend_reason(client, db_engine):
    ac, seed = client
    headers = await _platform_headers(ac, db_engine)
    tid = seed["t1"].id

    # Put customer into grace so extend_trial reopens trial (metadata lifecycle).
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as db:
        t = await db.get(m.Tenant, tid)
        t.status = "grace"
        t.grace_ends_at = __import__("datetime").datetime.utcnow() + __import__(
            "datetime"
        ).timedelta(days=2)
        await db.commit()

    detail = await ac.get(f"/api/v1/platform/tenants/{tid}", headers=headers)
    assert detail.status_code == 200, detail.text
    data = detail.json()["data"]
    assert "trial_ends_at" in data or "days_remaining" in data
    assert "grace_ends_at" in data
    assert data["status"] == "grace"

    ext = await ac.patch(
        f"/api/v1/platform/tenants/{tid}/lifecycle",
        headers=headers,
        json={"extend_trial_days": 10},
    )
    assert ext.status_code == 200, ext.text
    assert ext.json()["data"]["status"] == "trial"
    assert ext.json()["data"].get("billing_deferred") is True
    assert ext.json()["data"].get("trial_ends_at")

    sus = await ac.post(
        f"/api/v1/platform/tenants/{tid}/suspend",
        headers=headers,
        json={"reason": "Ops hold for Stage 88"},
    )
    assert sus.status_code == 200, sus.text
    assert sus.json()["data"]["status"] == "suspended"
    assert sus.json()["data"]["suspended_reason"] == "Ops hold for Stage 88"


@pytest.mark.asyncio
async def test_tenant_cannot_extend_lifecycle(client, db_engine):
    ac, seed = client
    mgr = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    r = await ac.patch(
        f"/api/v1/platform/tenants/{seed['t1'].id}/lifecycle",
        headers=mgr,
        json={"extend_trial_days": 7},
    )
    assert r.status_code == 403


def test_tenant_detail_ui_has_lifecycle_controls():
    page = (ROOT / "frontend/app/platform/tenants/[id]/page.tsx").read_text(encoding="utf-8")
    assert "/lifecycle" in page
    assert "extend_trial_days" in page or "Extend trial" in page
    assert "suspendReason" in page or "Suspend reason" in page
    assert "trial_ends_at" in page and "days_remaining" in page
