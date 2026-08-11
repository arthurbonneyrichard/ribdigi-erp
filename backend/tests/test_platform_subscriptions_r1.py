"""Stage 85 R1 — Platform subscriptions roster (metadata honesty)."""

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
            email="subs-ops@ribdigi.example.com",
            full_name="Subs Ops",
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
            "email": "subs-ops@ribdigi.example.com",
            "password": "SecurePass123!",
            "tenant_id": "ribdigi-platform",
            "totp_code": code,
        },
    )
    assert login.status_code == 200, login.text
    token = login.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}", "X-Tenant-ID": PLATFORM_TENANT_ID}


@pytest.mark.asyncio
async def test_platform_subscriptions_roster_no_fake_mrr(client, db_engine):
    ac, _seed = client
    headers = await _platform_headers(ac, db_engine)
    r = await ac.get("/api/v1/platform/subscriptions", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data.get("deferred_billing") is True
    assert data.get("mrr") is None
    assert data.get("checkout_enabled") is False
    assert data.get("subscriptions_live") is False
    assert isinstance(data.get("items"), list)
    assert data.get("total") == len(data["items"])
    # Customer seed tenants present; platform tenant excluded
    slugs = {row["slug"] for row in data["items"]}
    assert "ribdigi-platform" not in slugs
    assert "alpha" in slugs or len(data["items"]) >= 1
    for row in data["items"]:
        assert "plan_code" in row and "status" in row
        assert row.get("billing") == "deferred"


@pytest.mark.asyncio
async def test_platform_billing_includes_roster(client, db_engine):
    ac, _seed = client
    headers = await _platform_headers(ac, db_engine)
    r = await ac.get("/api/v1/platform/billing", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data.get("deferred") is True
    assert data.get("mrr") is None
    assert data.get("subscriptions_live") is False
    assert isinstance(data.get("active_subscriptions"), list)


@pytest.mark.asyncio
async def test_tenant_cannot_access_platform_subscriptions(client):
    ac, _seed = client
    mgr = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    r = await ac.get("/api/v1/platform/subscriptions", headers=mgr)
    assert r.status_code == 403


def test_platform_billing_page_shows_roster():
    page = (ROOT / "frontend/app/platform/billing/page.tsx").read_text(encoding="utf-8")
    assert "Subscriptions roster" in page or "subscriptions" in page
    assert "/platform/subscriptions" in page or "active_subscriptions" in page
