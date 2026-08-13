"""Expense branch/department assignment (BR-9.2)."""

from __future__ import annotations

import pyotp
import pytest

from app import models as m
from tests.conftest import auth_headers


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_expense_branch_department_create_patch_and_validation(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    tenant_id = seed["t1"].id
    # Keep create under pending so PATCH org dims is allowed (approved rows are locked).
    seed["t1"].expense_approval_threshold = 1
    await db_session.commit()

    branch = m.Branch(tenant_id=tenant_id, code="HQ", name="Head Office", is_active=True)
    other = m.Branch(tenant_id=tenant_id, code="EAST", name="East", is_active=True)
    db_session.add_all([branch, other])
    await db_session.flush()
    dept = m.Department(
        tenant_id=tenant_id,
        code="FIN",
        name="Finance",
        branch_id=branch.id,
        is_active=True,
    )
    wrong_dept = m.Department(
        tenant_id=tenant_id,
        code="OPS",
        name="Ops",
        branch_id=other.id,
        is_active=True,
    )
    db_session.add_all([dept, wrong_dept])
    await db_session.commit()

    cats = await ac.get("/api/v1/expenses/categories", headers=headers)
    assert cats.status_code == 200
    cat_id = cats.json()["data"][0]["id"]

    created = await ac.post(
        "/api/v1/expenses",
        headers=headers,
        json={
            "category_id": cat_id,
            "amount": 25,
            "description": "Office supplies",
            "branch_id": branch.id,
            "department_id": dept.id,
        },
    )
    assert created.status_code == 200, created.text
    data = created.json()["data"]
    assert data["branch_id"] == branch.id
    assert data["department_id"] == dept.id
    eid = data["id"]

    listed = await ac.get("/api/v1/expenses", headers=headers)
    assert any(r["id"] == eid and r["branch_id"] == branch.id for r in listed.json()["data"])

    mismatched = await ac.post(
        "/api/v1/expenses",
        headers=headers,
        json={
            "category_id": cat_id,
            "amount": 10,
            "description": "Bad org",
            "branch_id": branch.id,
            "department_id": wrong_dept.id,
        },
    )
    assert mismatched.status_code == 400

    cleared = await ac.patch(
        f"/api/v1/expenses/{eid}",
        headers=headers,
        json={"clear_department": True},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["data"]["department_id"] is None
    assert cleared.json()["data"]["branch_id"] == branch.id

    foreign = await ac.get(
        f"/api/v1/expenses/{eid}",
        headers={**headers, "X-Tenant-ID": seed["t2"].id},
    )
    assert foreign.status_code == 403
