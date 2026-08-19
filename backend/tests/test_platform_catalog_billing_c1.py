"""Stage 89 C1 — Plan catalog metadata + billing roster depth."""

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


async def _platform_headers(ac, db_engine, email="catalog-c1@ribdigi.example.com"):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as db:
        await ensure_platform_tenant(db)
        secret = pyotp.random_base32()
        user = m.User(
            tenant_id=PLATFORM_TENANT_ID,
            email=email,
            full_name="Catalog C1",
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
async def test_plans_catalog_enriched_metadata(client, db_engine):
    ac, _seed = client
    headers = await _platform_headers(ac, db_engine)
    r = await ac.get("/api/v1/platform/plans", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["deferred_billing"] is True
    assert data["checkout_enabled"] is False
    assert data.get("subscriptions_live") is False
    assert data["mrr"] is None
    catalog = data.get("catalog") or []
    assert len(catalog) >= 4
    codes = {c["code"] for c in catalog}
    assert "trial" in codes and "starter" in codes
    trial = next(c for c in catalog if c["code"] == "trial")
    assert trial.get("label")
    assert "soft_limits" in trial


@pytest.mark.asyncio
async def test_subscriptions_roster_has_trial_ends(client, db_engine):
    ac, _seed = client
    headers = await _platform_headers(ac, db_engine, email="catalog-c1b@ribdigi.example.com")
    r = await ac.get("/api/v1/platform/subscriptions", headers=headers)
    assert r.status_code == 200, r.text
    items = r.json()["data"]["items"]
    assert items
    assert "trial_ends_at" in items[0]
    assert items[0].get("billing") == "deferred"


def test_plans_and_billing_ui_depth():
    plans = (ROOT / "frontend/app/platform/plans/page.tsx").read_text(encoding="utf-8")
    assert "catalog" in plans
    assert "soft_limits" in plans or "Soft limits" in plans
    assert "ADR-002" in plans
    billing = (ROOT / "frontend/app/platform/billing/page.tsx").read_text(encoding="utf-8")
    assert "trial_ends_at" in billing
    assert "/platform/tenants/" in billing
