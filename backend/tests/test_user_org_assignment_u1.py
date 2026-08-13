"""User branch/department/record_scope assignment (BR-3.1 / BR-3.3)."""

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
async def test_user_create_and_patch_org_assignment(client):
    ac, seed = client
    headers = await _admin(ac, seed)

    branch = await ac.post(
        "/api/v1/branches",
        headers=headers,
        json={"code": "U1BR", "name": "User Branch"},
    )
    assert branch.status_code == 200, branch.text
    branch_id = branch.json()["data"]["id"]

    dept = await ac.post(
        "/api/v1/departments",
        headers=headers,
        json={"code": "U1DEP", "name": "User Dept", "branch_id": branch_id},
    )
    assert dept.status_code == 200, dept.text
    dept_id = dept.json()["data"]["id"]

    created = await ac.post(
        "/api/v1/users",
        headers=headers,
        json={
            "email": "orguser@alpha.example.com",
            "full_name": "Org User",
            "password": "SecurePass123!",
            "role": "cashier",
            "phone": "+233200000111",
            "branch_id": branch_id,
            "department_id": dept_id,
            "record_scope": "department",
        },
    )
    assert created.status_code == 200, created.text
    user = created.json()["data"]["user"]
    assert user["branch_id"] == branch_id
    assert user["department_id"] == dept_id
    assert user["record_scope"] == "department"
    assert user["phone"] == "+233200000111"
    uid = user["id"]

    listed = await ac.get("/api/v1/users", headers=headers)
    assert listed.status_code == 200
    row = next(u for u in listed.json()["data"] if u["id"] == uid)
    assert row["branch_id"] == branch_id
    assert row["department_id"] == dept_id

    cleared = await ac.patch(
        f"/api/v1/users/{uid}",
        headers=headers,
        json={"clear_department": True, "clear_branch": True, "record_scope": "own"},
    )
    assert cleared.status_code == 200, cleared.text
    cuser = cleared.json()["data"]
    assert cuser["branch_id"] is None
    assert cuser["department_id"] is None
    assert cuser["record_scope"] == "own"

    reassigned = await ac.patch(
        f"/api/v1/users/{uid}",
        headers=headers,
        json={"branch_id": branch_id, "department_id": dept_id, "record_scope": "branch"},
    )
    assert reassigned.status_code == 200, reassigned.text
    assert reassigned.json()["data"]["branch_id"] == branch_id
    assert reassigned.json()["data"]["department_id"] == dept_id
    assert reassigned.json()["data"]["record_scope"] == "branch"
