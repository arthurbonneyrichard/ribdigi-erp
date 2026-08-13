"""Branch management profile fields and soft deactivate (BR-2.2)."""

from __future__ import annotations

import pyotp
import pytest

from tests.conftest import auth_headers


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_branch_create_edit_clear_manager_and_deactivate(client):
    ac, seed = client
    headers = await _admin(ac, seed)

    created = await ac.post(
        "/api/v1/branches",
        headers=headers,
        json={
            "code": "ACC",
            "name": "Accra Branch",
            "address": "Ring Road",
            "phone": "+233201111111",
            "email": "accra@alpha.example.com",
            "manager_id": seed["mgr1"].id,
        },
    )
    assert created.status_code == 200, created.text
    data = created.json()["data"]
    assert data["code"] == "ACC"
    assert data["address"] == "Ring Road"
    assert data["phone"] == "+233201111111"
    assert data["email"] == "accra@alpha.example.com"
    assert data["manager_id"] == seed["mgr1"].id
    assert data["is_active"] is True
    bid = data["id"]

    listed = await ac.get("/api/v1/branches", headers=headers)
    assert listed.status_code == 200
    assert any(r["id"] == bid for r in listed.json()["data"])

    patched = await ac.patch(
        f"/api/v1/branches/{bid}",
        headers=headers,
        json={
            "name": "Accra Central",
            "address": "Independence Ave",
            "phone": "+233202222222",
            "email": "central@alpha.example.com",
            "clear_manager": True,
        },
    )
    assert patched.status_code == 200, patched.text
    pdata = patched.json()["data"]
    assert pdata["name"] == "Accra Central"
    assert pdata["address"] == "Independence Ave"
    assert pdata["phone"] == "+233202222222"
    assert pdata["email"] == "central@alpha.example.com"
    assert pdata["manager_id"] is None

    deactivated = await ac.patch(
        f"/api/v1/branches/{bid}",
        headers=headers,
        json={"is_active": False},
    )
    assert deactivated.status_code == 200
    assert deactivated.json()["data"]["is_active"] is False

    active_only = await ac.get("/api/v1/branches?active_only=true", headers=headers)
    assert active_only.status_code == 200
    assert not any(r["id"] == bid for r in active_only.json()["data"])

    # Soft-deactivate keeps the row for history / store links
    all_rows = await ac.get("/api/v1/branches", headers=headers)
    assert any(r["id"] == bid and r["is_active"] is False for r in all_rows.json()["data"])

    dup = await ac.post(
        "/api/v1/branches",
        headers=headers,
        json={"code": "ACC", "name": "Dup"},
    )
    assert dup.status_code == 409
