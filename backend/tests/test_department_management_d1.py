"""Department management create/edit/head/deactivate (BR-2.5)."""

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
async def test_department_create_edit_clear_head_and_deactivate(client):
    ac, seed = client
    headers = await _admin(ac, seed)

    branch = await ac.post(
        "/api/v1/branches",
        headers=headers,
        json={"code": "HQ-D", "name": "HQ for Depts"},
    )
    assert branch.status_code == 200, branch.text
    branch_id = branch.json()["data"]["id"]

    created = await ac.post(
        "/api/v1/departments",
        headers=headers,
        json={
            "code": "SALES",
            "name": "Sales",
            "branch_id": branch_id,
            "head_user_id": seed["mgr1"].id,
        },
    )
    assert created.status_code == 200, created.text
    data = created.json()["data"]
    assert data["code"] == "SALES"
    assert data["branch_id"] == branch_id
    assert data["head_user_id"] == seed["mgr1"].id
    assert data["is_active"] is True
    did = data["id"]

    listed = await ac.get("/api/v1/departments", headers=headers)
    assert listed.status_code == 200
    assert any(r["id"] == did for r in listed.json()["data"])

    by_branch = await ac.get(f"/api/v1/departments?branch_id={branch_id}", headers=headers)
    assert by_branch.status_code == 200
    assert any(r["id"] == did for r in by_branch.json()["data"])

    patched = await ac.patch(
        f"/api/v1/departments/{did}",
        headers=headers,
        json={
            "name": "Sales & CRM",
            "clear_head": True,
            "clear_branch": True,
        },
    )
    assert patched.status_code == 200, patched.text
    pdata = patched.json()["data"]
    assert pdata["name"] == "Sales & CRM"
    assert pdata["head_user_id"] is None
    assert pdata["branch_id"] is None

    deactivated = await ac.patch(
        f"/api/v1/departments/{did}",
        headers=headers,
        json={"is_active": False},
    )
    assert deactivated.status_code == 200
    assert deactivated.json()["data"]["is_active"] is False

    active_only = await ac.get("/api/v1/departments?active_only=true", headers=headers)
    assert active_only.status_code == 200
    assert not any(r["id"] == did for r in active_only.json()["data"])

    dup = await ac.post(
        "/api/v1/departments",
        headers=headers,
        json={"code": "SALES", "name": "Dup"},
    )
    assert dup.status_code == 409
