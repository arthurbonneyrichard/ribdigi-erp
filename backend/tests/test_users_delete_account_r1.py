"""Tenant user hard-delete from company dashboard Users page."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_users_delete_account_ui_wired():
    page = (ROOT / "frontend/app/(dashboard)/users/page.tsx").read_text(encoding="utf-8")
    assert "async function deleteUser" in page
    assert "/account" in page and "DELETE" in page
    assert 'aria-label={`Delete user ${r.email}`}' in page
    assert "deleteUser(r)" in page


@pytest.mark.asyncio
async def test_company_admin_can_delete_staff_account(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:8]
    created = await ac.post(
        "/api/v1/users",
        headers=admin,
        json={
            "email": f"del-user-{suffix}@alpha.example.com",
            "full_name": f"Delete Staff {suffix}",
            "password": "SecurePass123!",
            "role": "cashier",
        },
    )
    assert created.status_code == 200, created.text
    uid = created.json()["data"]["id"]

    deleted = await ac.delete(f"/api/v1/users/{uid}/account", headers=admin)
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["data"]["id"] == uid

    listed = await ac.get("/api/v1/users", headers=admin)
    assert listed.status_code == 200, listed.text
    ids = {row["id"] for row in listed.json()["data"]}
    assert uid not in ids

    missing = await ac.delete(f"/api/v1/users/{uid}/account", headers=admin)
    assert missing.status_code == 404, missing.text


@pytest.mark.asyncio
async def test_cannot_delete_own_user_account(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    me = await ac.get("/api/v1/me", headers=admin)
    assert me.status_code == 200, me.text
    my_id = me.json()["data"]["id"]
    resp = await ac.delete(f"/api/v1/users/{my_id}/account", headers=admin)
    assert resp.status_code == 400, resp.text
    assert "own" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_deactivate_still_soft_deletes(client, seeded):
    """Existing DELETE /users/{id} remains soft-deactivate."""
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:8]
    created = await ac.post(
        "/api/v1/users",
        headers=admin,
        json={
            "email": f"soft-{suffix}@alpha.example.com",
            "full_name": f"Soft {suffix}",
            "password": "SecurePass123!",
            "role": "cashier",
        },
    )
    assert created.status_code == 200, created.text
    uid = created.json()["data"]["id"]
    deactivated = await ac.delete(f"/api/v1/users/{uid}", headers=admin)
    assert deactivated.status_code == 200, deactivated.text
    assert deactivated.json()["data"]["is_active"] is False
    assert deactivated.json()["data"]["id"] == uid
