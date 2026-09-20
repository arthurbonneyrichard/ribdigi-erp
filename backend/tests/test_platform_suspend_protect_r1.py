"""Platform workspace cannot be suspended; login recovery when mistakenly locked."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from app import models as m
from app.rbac import permissions_for_role
from app.security import hash_password
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_platform_suspend_protect_ui_wired():
    plat = (ROOT / "frontend/app/(dashboard)/platform/page.tsx").read_text(encoding="utf-8")
    assert "t.slug !== 'platform' && t.slug !== 'ribdigi-platform'" in plat
    assert "aria-label={`Suspend tenant ${t.id}`}" in plat
    assert "aria-label={`Activate tenant ${t.id}`}" in plat


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_platform_workspace_cannot_be_suspended(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)

    platform = m.Tenant(
        id="ribdigi-platform",
        slug="ribdigi-platform",
        company_name="Ribdigi House",
        status="active",
        industry="retail",
        package_code="trial",
    )
    db_session.add(platform)
    await db_session.commit()

    resp = await ac.post(
        "/api/v1/tenants/ribdigi-platform/suspend",
        headers=headers,
        json={"reason": "Mistaken suspend should be rejected"},
    )
    assert resp.status_code == 400, resp.text
    assert "cannot be suspended" in resp.text.lower()


@pytest.mark.asyncio
async def test_platform_owner_login_and_activate_when_suspended(client, db_session):
    ac, _seed = client

    platform = m.Tenant(
        id="ribdigi-platform",
        slug="ribdigi-platform",
        company_name="Ribdigi House",
        status="suspended",
        industry="retail",
        package_code="trial",
        suspended_reason="Mistaken suspend fixture",
    )
    owner = m.User(
        tenant_id="ribdigi-platform",
        email="owner@ribdigihouse.example.com",
        full_name="Platform Owner",
        password_hash=hash_password("SecurePass123!"),
        role="platform_owner",
        email_verified=True,
        permissions=permissions_for_role("platform_owner"),
        totp_enabled=False,
    )
    db_session.add_all([platform, owner])
    await db_session.commit()

    login = await ac.post(
        "/api/v1/auth/login",
        json={
            "email": "owner@ribdigihouse.example.com",
            "password": "SecurePass123!",
            "tenant_id": "ribdigi-platform",
        },
    )
    assert login.status_code == 200, login.text
    token = login.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    act = await ac.post("/api/v1/tenants/me/activate", headers=headers, json={})
    assert act.status_code == 200, act.text
    assert act.json()["data"]["status"] == "active"
    assert act.json()["data"].get("suspended_reason") in (None, "")
