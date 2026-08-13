"""Store manager and branch assignment (BR-2.3)."""

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
async def test_store_manager_and_branch_create_patch_clear(client):
    ac, seed = client
    headers = await _admin(ac, seed)
    manager_id = seed["mgr1"].id

    branch = await ac.post(
        "/api/v1/branches",
        headers=headers,
        json={"code": "BR-ST", "name": "Store Branch"},
    )
    assert branch.status_code == 200, branch.text
    branch_id = branch.json()["data"]["id"]

    created = await ac.post(
        "/api/v1/stores",
        headers=headers,
        json={
            "name": "Managed Store",
            "code": "MGR-1",
            "address": "10 Market St",
            "manager_id": manager_id,
            "branch_id": branch_id,
        },
    )
    assert created.status_code == 200, created.text
    data = created.json()["data"]
    assert data["manager_id"] == manager_id
    assert data["branch_id"] == branch_id
    sid = data["id"]

    got = await ac.get(f"/api/v1/stores/{sid}", headers=headers)
    assert got.status_code == 200
    assert got.json()["data"]["manager_id"] == manager_id
    assert got.json()["data"]["branch_id"] == branch_id

    reassigned = await ac.patch(
        f"/api/v1/stores/{sid}",
        headers=headers,
        json={"manager_id": seed["super"].id},
    )
    assert reassigned.status_code == 200, reassigned.text
    assert reassigned.json()["data"]["manager_id"] == seed["super"].id

    cleared = await ac.patch(
        f"/api/v1/stores/{sid}",
        headers=headers,
        json={"clear_manager": True, "clear_branch": True},
    )
    assert cleared.status_code == 200, cleared.text
    cdata = cleared.json()["data"]
    assert cdata["manager_id"] is None
    assert cdata["branch_id"] is None

    bad_user = await ac.patch(
        f"/api/v1/stores/{sid}",
        headers=headers,
        json={"manager_id": "missing-user"},
    )
    assert bad_user.status_code == 404

    bad_branch = await ac.post(
        "/api/v1/stores",
        headers=headers,
        json={
            "name": "Bad Branch Store",
            "code": "MGR-BAD",
            "branch_id": "missing-branch",
        },
    )
    assert bad_branch.status_code == 404
