"""Stage 93 M1 — Roster navigation & export."""

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


async def _platform_headers(ac, db_engine, email="roster-m1@ribdigi.example.com"):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as db:
        await ensure_platform_tenant(db)
        secret = pyotp.random_base32()
        user = m.User(
            tenant_id=PLATFORM_TENANT_ID,
            email=email,
            full_name="Roster M1",
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
async def test_industries_notes_search_month_pdf(client, db_engine):
    ac, seed = client
    headers = await _platform_headers(ac, db_engine)
    tid = seed["t1"].id

    industries = await ac.get("/api/v1/platform/industries", headers=headers)
    assert industries.status_code == 200, industries.text
    codes = industries.json()["data"]["codes"]
    assert "retail" in codes

    bad = await ac.post(
        "/api/v1/platform/tenants",
        headers=headers,
        json={
            "company_name": "Bad Industry Co",
            "slug": "bad-industry-m1",
            "admin_email": "bad-ind-m1@example.com",
            "admin_password": "SecurePass123!",
            "industry": "not-a-real-industry",
        },
    )
    assert bad.status_code == 400

    notes = await ac.patch(
        f"/api/v1/platform/tenants/{tid}/notes",
        headers=headers,
        json={"platform_notes": "x" * 2001},
    )
    assert notes.status_code == 422

    await ac.post(
        f"/api/v1/platform/tenants/{tid}/suspend",
        headers=headers,
        json={"reason": "stage93-suspend-marker"},
    )
    found = await ac.get(
        "/api/v1/platform/tenants?q=stage93-suspend-marker",
        headers=headers,
    )
    assert found.status_code == 200, found.text
    assert tid in {i["id"] for i in found.json()["data"]["items"]}

    month = await ac.get(
        "/api/v1/platform/tenants?created_this_month=true",
        headers=headers,
    )
    assert month.status_code == 200, month.text
    assert month.json()["data"]["filters"].get("created_this_month") is True

    await ac.post(
        f"/api/v1/platform/tenants/{tid}/admin/password-reset-email",
        headers=headers,
        json={},
    )
    pdf = await ac.get("/api/v1/platform/tenants/export?format=pdf", headers=headers)
    assert pdf.status_code == 200, pdf.text
    assert "application/pdf" in pdf.headers.get("content-type", "")
    assert b"last_email=" in pdf.content or b"sent=" in pdf.content


def test_dashboard_tenants_billing_ui_m1():
    dash = (ROOT / "frontend/app/platform/dashboard/page.tsx").read_text(encoding="utf-8")
    assert "/platform/tenants?created_this_month=true" in dash
    assert 'href="/platform/tenants"' in dash or "href=\"/platform/tenants\"" in dash
    tenants = (ROOT / "frontend/app/platform/tenants/page.tsx").read_text(encoding="utf-8")
    assert "/platform/industries" in tenants
    assert "created_this_month" in tenants
    assert "syncUrl" in tenants
    assert "focusAtRisk" in tenants or "at-risk-queue" in tenants
    assert "2000" in (ROOT / "frontend/app/platform/tenants/[id]/page.tsx").read_text(
        encoding="utf-8"
    )
    billing = (ROOT / "frontend/app/platform/billing/page.tsx").read_text(encoding="utf-8")
    assert "grace_ends_at" in billing
