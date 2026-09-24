"""Platform staff DELETE account (owner Staff directory)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_platform_staff_delete_ui_wired():
    staff = (ROOT / "frontend/app/(dashboard)/platform/staff/page.tsx").read_text(encoding="utf-8")
    assert "async function deleteStaff" in staff
    assert 'method: \'DELETE\'' in staff or 'method: "DELETE"' in staff
    assert "/platform/staff/${String(row.id).trim()}" in staff or "`/platform/staff/${String(row.id).trim()}`" in staff
    assert 'aria-label={`Delete platform staff ${u.email}`}' in staff
    assert 'className="btn-danger"' in staff and "deleteStaff(u)" in staff
    assert "Cannot delete your own account" in staff or "cannot delete your own account" in staff.lower()


@pytest.mark.asyncio
async def test_platform_staff_delete_api(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:8]
    created = await ac.post(
        "/api/v1/platform/staff",
        headers=admin,
        json={
            "email": f"del-staff-{suffix}@example.com",
            "full_name": f"Delete Me {suffix}",
            "password": "SecurePass123!",
            "role": "platform_support",
        },
    )
    assert created.status_code == 200, created.text
    uid = created.json()["data"]["id"]

    deleted = await ac.delete(f"/api/v1/platform/staff/{uid}", headers=admin)
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["data"]["id"] == uid
    assert deleted.json()["data"]["email"] == f"del-staff-{suffix}@example.com"

    listed = await ac.get("/api/v1/platform/staff", headers=admin)
    assert listed.status_code == 200, listed.text
    ids = {row["id"] for row in listed.json()["data"]}
    assert uid not in ids

    missing = await ac.delete(f"/api/v1/platform/staff/{uid}", headers=admin)
    assert missing.status_code == 404, missing.text


@pytest.mark.asyncio
async def test_platform_staff_cannot_delete_self(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    me = await ac.get("/api/v1/me", headers=admin)
    assert me.status_code == 200, me.text
    my_id = me.json()["data"]["id"]
    resp = await ac.delete(f"/api/v1/platform/staff/{my_id}", headers=admin)
    assert resp.status_code == 400, resp.text
    assert "own" in resp.json()["detail"].lower()
