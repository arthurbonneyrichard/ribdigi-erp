"""Stage 92 G1 — Roster triage + commercial-metadata context."""

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


async def _platform_headers(ac, db_engine, email="roster-g1@ribdigi.example.com"):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as db:
        await ensure_platform_tenant(db)
        secret = pyotp.random_base32()
        user = m.User(
            tenant_id=PLATFORM_TENANT_ID,
            email=email,
            full_name="Roster G1",
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
async def test_notes_search_list_delivery_and_roster(client, db_engine):
    ac, seed = client
    headers = await _platform_headers(ac, db_engine)
    tid = seed["t1"].id

    notes = await ac.patch(
        f"/api/v1/platform/tenants/{tid}/notes",
        headers=headers,
        json={"platform_notes": "stage92-unique-note-marker"},
    )
    assert notes.status_code == 200, notes.text

    found = await ac.get(
        "/api/v1/platform/tenants?q=stage92-unique-note-marker",
        headers=headers,
    )
    assert found.status_code == 200, found.text
    ids = {i["id"] for i in found.json()["data"]["items"]}
    assert tid in ids

    assist = await ac.post(
        f"/api/v1/platform/tenants/{tid}/admin/password-reset-email",
        headers=headers,
        json={},
    )
    assert assist.status_code == 200, assist.text

    listed = await ac.get("/api/v1/platform/tenants", headers=headers)
    assert listed.status_code == 200, listed.text
    row = next(i for i in listed.json()["data"]["items"] if i["id"] == tid)
    assert row.get("last_house_email_delivery") is not None
    assert row["last_house_email_delivery"].get("fabricated_success") is False

    exported = await ac.get("/api/v1/platform/tenants/export?format=csv", headers=headers)
    assert exported.status_code == 200, exported.text
    assert "last_house_email_at" in exported.text

    roster = await ac.get("/api/v1/platform/subscriptions", headers=headers)
    assert roster.status_code == 200, roster.text
    body = roster.json()["data"]
    assert body.get("mrr") is None
    assert body.get("subscriptions_live") is False
    item = next(i for i in body["items"] if i["tenant_id"] == tid)
    assert "industry" in item
    assert "admin_email" in item
    assert "user_count" in item
    assert "store_count" in item
    assert "created_at" in item


def test_dashboard_tenants_billing_ui_wiring():
    dash = (ROOT / "frontend/app/platform/dashboard/page.tsx").read_text(encoding="utf-8")
    assert "/platform/tenants?status=active" in dash
    assert "/platform/tenants?status=trial" in dash
    tenants = (ROOT / "frontend/app/platform/tenants/page.tsx").read_text(encoding="utf-8")
    assert "platform_notes" in tenants or "notes" in tenants
    assert "last_house_email_delivery" in tenants
    assert "/platform/plans" in tenants
    assert "soft_limits" in tenants
    billing = (ROOT / "frontend/app/platform/billing/page.tsx").read_text(encoding="utf-8")
    assert "admin_email" in billing
    assert "user_count" in billing
