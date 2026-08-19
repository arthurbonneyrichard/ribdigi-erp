"""Stage 83 U1 — Tenant Admin user-ops (password reset + org assignment)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from app import models as m
from app.security import verify_password
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_admin_can_reset_user_password(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)
    user_id = seed["u1"].id
    r = await ac.patch(
        f"/api/v1/users/{user_id}",
        headers=headers,
        json={"password": "NewSecurePass456!"},
    )
    assert r.status_code == 200, r.text
    await db_session.refresh(seed["u1"])
    assert verify_password("NewSecurePass456!", seed["u1"].password_hash)


@pytest.mark.asyncio
async def test_admin_can_update_branch_assignment(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)
    tid = seed["t1"].id
    branch = m.Branch(tenant_id=tid, name="HQ", code="HQ")
    db_session.add(branch)
    await db_session.commit()
    await db_session.refresh(branch)

    user_id = seed["u1"].id
    r = await ac.patch(
        f"/api/v1/users/{user_id}",
        headers=headers,
        json={"branch_id": branch.id},
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["branch_id"] == branch.id


def test_users_ui_has_reset_password_and_org_controls():
    text = (ROOT / "frontend/app/users/page.tsx").read_text(encoding="utf-8")
    assert "Reset password" in text
    assert "resetPassword" in text
    assert "setOrg" in text
    assert "Branch" in text and "Department" in text
