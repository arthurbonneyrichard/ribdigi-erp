"""Stage 21 T1: Tenant registration & lifecycle fidelity (BR-1.1–1.3)."""

from __future__ import annotations

import io
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select

from app import models as m
from app import tenants as tenants_svc
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def _png() -> bytes:
    return b"\x89PNG\r\n\x1a\n" + b"fake-png-bytes"


async def _register(ac, *, slug: str, email: str, industry: str = "retail"):
    r = await ac.post(
        "/api/v1/tenants",
        json={
            "company_name": f"{slug.title()} Co",
            "slug": slug,
            "industry": industry,
            "currency": "GHS",
            "timezone": "Africa/Accra",
            "admin_email": email,
            "admin_password": "SecurePass123!",
            "admin_full_name": "New Admin",
        },
    )
    return r


@pytest.mark.asyncio
async def test_register_trial_verify_and_slug_unique(client, db_session):
    """BR-1.1: register company/email/password/industry → trial + verification; slug unique."""
    ac, _seed = client

    created = await _register(
        ac, slug="gamma-t1", email="admin@gamma-t1.example.com", industry="pharmacy"
    )
    assert created.status_code == 200, created.text
    body = created.json()["data"]
    assert body["status"] == "trial"
    assert body["slug"] == "gamma-t1"
    assert body.get("email_verification_token")
    assert body.get("email", {}).get("mode")  # console/smtp path present

    tenant = (
        await db_session.execute(select(m.Tenant).where(m.Tenant.slug == "gamma-t1"))
    ).scalar_one()
    assert tenant.status == "trial"
    assert tenant.industry == "pharmacy"
    assert tenant.trial_ends_at is not None
    assert tenant.trial_ends_at > datetime.utcnow()

    admin = (
        await db_session.execute(
            select(m.User).where(
                m.User.tenant_id == tenant.id,
                m.User.email == "admin@gamma-t1.example.com",
            )
        )
    ).scalar_one()
    assert admin.email_verified is False
    assert admin.role == "company_admin"

    # Email verification link path
    verify = await ac.post(
        "/api/v1/auth/verify-email",
        json={"token": body["email_verification_token"]},
    )
    assert verify.status_code == 200, verify.text
    assert verify.json()["data"]["verified"] is True
    await db_session.refresh(admin)
    assert admin.email_verified is True

    # Login works after verify
    login = await ac.post(
        "/api/v1/auth/login",
        json={
            "email": "admin@gamma-t1.example.com",
            "password": "SecurePass123!",
            "tenant_id": "gamma-t1",
        },
    )
    assert login.status_code == 200, login.text

    # Slug uniqueness
    dup = await _register(ac, slug="gamma-t1", email="other@gamma-t1.example.com")
    assert dup.status_code == 409

    # Tenant-scoped admin email uniqueness (DB UniqueConstraint tenant_id+email)
    from app.security import hash_password
    from sqlalchemy.exc import IntegrityError

    db_session.add(
        m.User(
            tenant_id=tenant.id,
            email="admin@gamma-t1.example.com",
            full_name="Dup",
            password_hash=hash_password("SecurePass123!"),
            role="cashier",
            email_verified=True,
            permissions={},
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_company_profile_industry_currency_logo(client, tmp_path, monkeypatch):
    """BR-1.2: profile fields + industry list + logo upload/display."""
    from app import storage as storage_svc

    monkeypatch.setattr(storage_svc.settings, "MEDIA_DIR", str(tmp_path))
    monkeypatch.setattr(storage_svc.settings, "STORAGE_BACKEND", "local")

    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    for industry in (
        "retail",
        "pharmacy",
        "restaurant",
        "bakery",
        "wholesale",
        "manufacturing",
    ):
        r = await ac.patch(
            "/api/v1/tenants/me",
            headers=headers,
            json={"industry": industry},
        )
        assert r.status_code == 200, r.text
        assert r.json()["data"]["industry"] == industry

    profile = await ac.patch(
        "/api/v1/tenants/me",
        headers=headers,
        json={
            "company_name": "Alpha Retail Updated",
            "address": "1 Market St",
            "phone": "+233200000001",
            "email": "hello@alpha.example.com",
            "website": "https://alpha.example.com",
            "fiscal_year_start": "04-01",
            "currency": "USD",
            "timezone": "UTC",
            "industry": "wholesale",
        },
    )
    assert profile.status_code == 200, profile.text
    data = profile.json()["data"]
    assert data["company_name"] == "Alpha Retail Updated"
    assert data["address"] == "1 Market St"
    assert data["phone"] == "+233200000001"
    assert data["email"] == "hello@alpha.example.com"
    assert data["website"] == "https://alpha.example.com"
    assert data["fiscal_year_start"] == "04-01"
    assert data["currency"] == "USD"
    assert data["timezone"] == "UTC"
    assert data["industry"] == "wholesale"

    up = await ac.post(
        "/api/v1/tenants/me/logo",
        headers=headers,
        files={"file": ("logo.png", io.BytesIO(_png()), "image/png")},
    )
    assert up.status_code == 200, up.text
    assert up.json()["data"]["has_logo"] is True
    got = await ac.get("/api/v1/tenants/me/logo", headers=headers)
    assert got.status_code == 200
    assert got.content[:8] == b"\x89PNG\r\n\x1a\n"


@pytest.mark.asyncio
async def test_subscription_statuses_reminders_grace_plan(client, db_session):
    """BR-1.3: Trial/Active/Suspended + 7/3/1 reminders + grace read-only + plan metadata."""
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    tenant = seed["t1"]

    # Activate from trial/active path
    if tenant.status != "active":
        act = await ac.post("/api/v1/tenants/me/activate", headers=headers)
        assert act.status_code == 200, act.text
        assert act.json()["data"]["status"] == "active"
    me = await ac.get("/api/v1/tenants/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["data"]["status"] == "active"

    # Plan upgrade/downgrade metadata (billing deferred — no payment)
    up = await ac.patch(
        "/api/v1/tenants/me",
        headers=headers,
        json={"plan_code": "growth"},
    )
    assert up.status_code == 200, up.text
    assert up.json()["data"]["plan_code"] == "growth"
    assert "billing deferred" in (up.json().get("message") or "").lower() or up.json()["data"][
        "plan_code"
    ] == "growth"
    down = await ac.patch(
        "/api/v1/tenants/me",
        headers=headers,
        json={"plan_code": "starter"},
    )
    assert down.status_code == 200
    assert down.json()["data"]["plan_code"] == "starter"

    # Trial reminders at 7 / 3 / 1 days
    tenant.status = "trial"
    tenant.trial_ends_at = datetime.utcnow() + timedelta(days=7)
    tenant.trial_notices = {}
    tenant.grace_ends_at = None
    await db_session.commit()
    result = await tenants_svc.process_trial_lifecycle(db_session)
    await db_session.commit()
    assert result["reminded"] >= 1
    await db_session.refresh(tenant)
    assert (tenant.trial_notices or {}).get("7")

    tenant.trial_ends_at = datetime.utcnow() + timedelta(days=3)
    await db_session.commit()
    await tenants_svc.process_trial_lifecycle(db_session)
    await db_session.commit()
    await db_session.refresh(tenant)
    assert (tenant.trial_notices or {}).get("3")

    tenant.trial_ends_at = datetime.utcnow() + timedelta(days=1)
    await db_session.commit()
    await tenants_svc.process_trial_lifecycle(db_session)
    await db_session.commit()
    await db_session.refresh(tenant)
    assert (tenant.trial_notices or {}).get("1")

    notes = (
        await db_session.execute(
            select(m.Notification).where(
                m.Notification.tenant_id == tenant.id,
                m.Notification.category == "billing",
            )
        )
    ).scalars().all()
    assert any("Trial ends in" in (n.title or "") for n in notes)

    # Expire trial → grace via lifecycle scanner
    tenant.status = "trial"
    tenant.trial_ends_at = datetime.utcnow() - timedelta(hours=1)
    tenant.grace_ends_at = None
    await db_session.commit()
    life = await tenants_svc.process_trial_lifecycle(db_session)
    await db_session.commit()
    await db_session.refresh(tenant)
    assert life["entered_grace"] >= 1
    assert tenant.status == "grace"
    assert tenant.grace_ends_at is not None
    assert tenant.grace_ends_at > datetime.utcnow()
    assert tenants_svc.is_read_only(tenant) is True
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        tenants_svc.assert_writable({"read_only": True})
    assert exc.value.status_code == 403
    assert exc.value.detail["code"] == "TENANT_READ_ONLY"

    # Ensure grace window is safely in the future for login (API uses a separate session)
    tenant.grace_ends_at = datetime.utcnow() + timedelta(days=7)
    await db_session.commit()

    # Grace login allowed; profile write blocked via read_only claim
    grace_h = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    me_grace = await ac.get("/api/v1/tenants/me", headers=grace_h)
    assert me_grace.status_code == 200, me_grace.text
    assert me_grace.json()["data"]["status"] == "grace"
    assert me_grace.json()["data"]["read_only"] is True
    blocked = await ac.patch(
        "/api/v1/tenants/me",
        headers=grace_h,
        json={"company_name": "Should Fail"},
    )
    assert blocked.status_code == 403
    detail = blocked.json().get("detail") or {}
    if isinstance(detail, dict):
        assert detail.get("code") == "TENANT_READ_ONLY"
    else:
        assert "read-only" in str(detail).lower() or "read_only" in str(detail).lower()

    # Activate from grace via service (platform path); then prove suspend blocks login
    await tenants_svc.activate_tenant(db_session, tenant)
    await db_session.commit()
    await db_session.refresh(tenant)
    assert tenant.status == "active"

    # ADR-137: cross-tenant HTTP suspend retired — use service (same as platform API)
    await tenants_svc.suspend_tenant(db_session, tenant, reason="Stage 21 T1 proof")
    await db_session.commit()
    await db_session.refresh(tenant)
    assert tenant.status == "suspended"
    denied = await ac.post(
        "/api/v1/auth/login",
        json={
            "email": "admin@alpha.example.com",
            "password": "SecurePass123!",
            "tenant_id": "alpha",
        },
    )
    assert denied.status_code == 403

    # Re-activate via service (suspended tenant blocks all JWT, including super_admin on same tenant)
    await db_session.refresh(tenant)
    await tenants_svc.activate_tenant(db_session, tenant)
    await db_session.commit()
    await db_session.refresh(tenant)
    assert tenant.status == "active"
    ok_login = await ac.post(
        "/api/v1/auth/login",
        json={
            "email": "admin@alpha.example.com",
            "password": "SecurePass123!",
            "tenant_id": "alpha",
        },
    )
    assert ok_login.status_code == 200, ok_login.text


def test_br_1_1_to_1_3_and_plan_synced():
    br = (ROOT / "docs" / "BUSINESS_REQUIREMENTS_DOCUMENT.md").read_text(encoding="utf-8")
    s11 = br.split("#### BR-1.1 Tenant Registration")[1].split("#### BR-1.2")[0]
    assert "[x] User can register with company name, email, password, industry type" in s11
    assert "[x] System validates email uniqueness" in s11
    assert "[x] System auto-creates isolated tenant database/schema" in s11
    assert "[x] System sends email verification link" in s11
    assert "[x] Tenant status defaults to \"Trial\"" in s11 or '[x] Tenant status defaults to "Trial"' in s11
    assert "Stage 21 T1" in s11
    assert "test_tenant_lifecycle_t1.py" in s11
    assert "ADR-001" in s11 or "shared-schema" in s11

    s12 = br.split("#### BR-1.2 Company Profile")[1].split("#### BR-1.3")[0]
    assert "[x] Upload and display company logo" in s12
    assert "[x] Edit company name, address, phone, email, website" in s12
    assert "[x] Configure fiscal year start date" in s12
    assert "[x] Set default currency and time zone" in s12
    assert "[x] Select industry from predefined list" in s12
    assert "Stage 21 T1" in s12

    s13 = br.split("#### BR-1.3 Subscription Plan Management")[1].split("#### BR-1.4")[0]
    assert "[x] Support statuses: Trial, Active, Suspended" in s13
    assert "[x] Automatic trial expiration notification" in s13
    assert "[x] Grace period handling" in s13
    assert "[x] Upgrade/downgrade plan capability" in s13
    assert "Stage 21 T1" in s13
    assert "billing" in s13.lower() or "ADR-002" in s13

    plan = (ROOT / "docs" / "STAGE_21_PLAN.md").read_text(encoding="utf-8")
    t1_line = [ln for ln in plan.splitlines() if "| **T1**" in ln][0]
    assert "COMPLETE" in t1_line
    assert "test_tenant_lifecycle_t1.py" in plan
