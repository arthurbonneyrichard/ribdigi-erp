"""Org units: branches, departments, and department/branch record scopes (BR-2.2 / BR-2.4 / BR-3.3)."""

from __future__ import annotations

import pyotp
import pytest
from sqlalchemy import select

from app import models as m
from app.expenses import create_expense, ensure_default_categories
from app.rbac import normalize_record_scope
from tests.conftest import auth_headers


async def _admin_headers(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


def test_normalize_record_scope_includes_org_units():
    assert normalize_record_scope("department") == "department"
    assert normalize_record_scope("branch") == "branch"
    assert normalize_record_scope("own") == "own"


@pytest.mark.asyncio
async def test_branch_and_department_crud(client):
    ac, seed = client
    headers = await _admin_headers(ac, seed)
    branch = await ac.post(
        "/api/v1/branches",
        headers=headers,
        json={"code": "HQ", "name": "Head Office", "address": "Accra"},
    )
    assert branch.status_code == 200, branch.text
    branch_id = branch.json()["data"]["id"]

    dept = await ac.post(
        "/api/v1/departments",
        headers=headers,
        json={"code": "FIN", "name": "Finance", "branch_id": branch_id},
    )
    assert dept.status_code == 200, dept.text

    listed = await ac.get("/api/v1/branches", headers=headers)
    assert any(r["code"] == "HQ" for r in listed.json()["data"])
    deps = await ac.get("/api/v1/departments", headers=headers)
    assert any(r["code"] == "FIN" for r in deps.json()["data"])

    store = await ac.post(
        "/api/v1/stores",
        headers=headers,
        json={"code": "S-HQ", "name": "HQ Store", "branch_id": branch_id},
    )
    assert store.status_code == 200, store.text
    assert store.json()["data"]["branch_id"] == branch_id


@pytest.mark.asyncio
async def test_branch_and_department_edit_and_soft_deactivate(client):
    ac, seed = client
    headers = await _admin_headers(ac, seed)

    branch = await ac.post(
        "/api/v1/branches",
        headers=headers,
        json={
            "code": "C7BR",
            "name": "C7 Branch",
            "phone": "+233200000001",
            "manager_id": seed["mgr1"].id,
        },
    )
    assert branch.status_code == 200, branch.text
    branch_id = branch.json()["data"]["id"]
    assert branch.json()["data"]["manager_id"] == seed["mgr1"].id

    updated = await ac.patch(
        f"/api/v1/branches/{branch_id}",
        headers=headers,
        json={"name": "C7 Branch Renamed", "phone": "+233200000099", "is_active": False},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["data"]["name"] == "C7 Branch Renamed"
    assert updated.json()["data"]["is_active"] is False

    listed = await ac.get("/api/v1/branches", headers=headers)
    assert listed.status_code == 200
    row = next(r for r in listed.json()["data"] if r["id"] == branch_id)
    assert row["is_active"] is False

    reactivated = await ac.patch(
        f"/api/v1/branches/{branch_id}",
        headers=headers,
        json={"is_active": True},
    )
    assert reactivated.status_code == 200
    assert reactivated.json()["data"]["is_active"] is True

    dept = await ac.post(
        "/api/v1/departments",
        headers=headers,
        json={
            "code": "C7DE",
            "name": "C7 Dept",
            "branch_id": branch_id,
            "head_user_id": seed["mgr1"].id,
        },
    )
    assert dept.status_code == 200, dept.text
    dept_id = dept.json()["data"]["id"]

    dept_upd = await ac.patch(
        f"/api/v1/departments/{dept_id}",
        headers=headers,
        json={"name": "C7 Dept Renamed", "is_active": False},
    )
    assert dept_upd.status_code == 200, dept_upd.text
    assert dept_upd.json()["data"]["name"] == "C7 Dept Renamed"
    assert dept_upd.json()["data"]["is_active"] is False

    foreign = await ac.patch(
        f"/api/v1/branches/{branch_id}",
        headers=headers,
        json={"manager_id": seed["u2"].id},
    )
    assert foreign.status_code == 404, foreign.text


@pytest.mark.asyncio
async def test_department_record_scope_peer_visibility(client, db_session):
    ac, seed = client
    headers = await _admin_headers(ac, seed)

    branch = await ac.post(
        "/api/v1/branches",
        headers=headers,
        json={"code": "BR1", "name": "Branch One"},
    )
    branch_id = branch.json()["data"]["id"]
    dept_a = await ac.post(
        "/api/v1/departments",
        headers=headers,
        json={"code": "SALES", "name": "Sales Dept", "branch_id": branch_id},
    )
    dept_b = await ac.post(
        "/api/v1/departments",
        headers=headers,
        json={"code": "OPS", "name": "Ops Dept", "branch_id": branch_id},
    )
    dept_a_id = dept_a.json()["data"]["id"]
    dept_b_id = dept_b.json()["data"]["id"]

    role = await ac.post(
        "/api/v1/roles",
        headers=headers,
        json={
            "key": "dept_clerk",
            "label": "Dept Clerk",
            "base_role": "cashier",
            "record_scope": "department",
            "permissions": {
                "dashboard": ["read"],
                "expenses": ["read", "write"],
                "notifications": ["read"],
                "security": ["read", "write"],
            },
        },
    )
    assert role.status_code == 200, role.text

    u1 = await ac.post(
        "/api/v1/users",
        headers=headers,
        json={
            "email": "clerk1@alpha.example.com",
            "full_name": "Clerk One",
            "password": "SecurePass123!",
            "role": "dept_clerk",
            "branch_id": branch_id,
            "department_id": dept_a_id,
        },
    )
    assert u1.status_code == 200, u1.text
    u2 = await ac.post(
        "/api/v1/users",
        headers=headers,
        json={
            "email": "clerk2@alpha.example.com",
            "full_name": "Clerk Two",
            "password": "SecurePass123!",
            "role": "dept_clerk",
            "branch_id": branch_id,
            "department_id": dept_a_id,
        },
    )
    assert u2.status_code == 200, u2.text
    u3 = await ac.post(
        "/api/v1/users",
        headers=headers,
        json={
            "email": "clerk3@alpha.example.com",
            "full_name": "Clerk Three",
            "password": "SecurePass123!",
            "role": "dept_clerk",
            "branch_id": branch_id,
            "department_id": dept_b_id,
        },
    )
    assert u3.status_code == 200, u3.text

    await ensure_default_categories(db_session, seed["t1"].id)
    cats = (
        await db_session.execute(
            select(m.ExpenseCategory).where(m.ExpenseCategory.tenant_id == seed["t1"].id)
        )
    ).scalars().all()

    e1 = await create_expense(
        db_session,
        tenant_id=seed["t1"].id,
        user_id=u1.json()["data"]["id"],
        amount=5,
        description="Dept A expense 1",
        category_id=cats[0].id if cats else None,
        payment_method="cash",
    )
    e2 = await create_expense(
        db_session,
        tenant_id=seed["t1"].id,
        user_id=u2.json()["data"]["id"],
        amount=6,
        description="Dept A expense 2",
        category_id=cats[0].id if cats else None,
        payment_method="cash",
    )
    e3 = await create_expense(
        db_session,
        tenant_id=seed["t1"].id,
        user_id=u3.json()["data"]["id"],
        amount=7,
        description="Dept B expense",
        category_id=cats[0].id if cats else None,
        payment_method="cash",
    )
    await db_session.commit()

    login = await ac.post(
        "/api/v1/auth/login",
        json={
            "email": "clerk1@alpha.example.com",
            "password": "SecurePass123!",
            "tenant_id": "alpha",
        },
    )
    assert login.status_code == 200, login.text
    token = login.json()["data"]["access_token"]
    tenant_id = login.json()["data"]["user"]["tenant_id"]
    h = {"Authorization": f"Bearer {token}", "X-Tenant-ID": tenant_id}

    listed = await ac.get("/api/v1/expenses", headers=h)
    assert listed.status_code == 200, listed.text
    ids = {row["id"] for row in listed.json()["data"]}
    assert e1.id in ids
    assert e2.id in ids
    assert e3.id not in ids

    missing = await ac.get(f"/api/v1/expenses/{e3.id}", headers=h)
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_branch_record_scope_peer_visibility(client, db_session):
    ac, seed = client
    headers = await _admin_headers(ac, seed)

    b1 = await ac.post(
        "/api/v1/branches",
        headers=headers,
        json={"code": "EAST", "name": "East Branch"},
    )
    b2 = await ac.post(
        "/api/v1/branches",
        headers=headers,
        json={"code": "WEST", "name": "West Branch"},
    )
    b1_id = b1.json()["data"]["id"]
    b2_id = b2.json()["data"]["id"]

    role = await ac.post(
        "/api/v1/roles",
        headers=headers,
        json={
            "key": "branch_clerk",
            "label": "Branch Clerk",
            "base_role": "cashier",
            "record_scope": "branch",
            "permissions": {
                "dashboard": ["read"],
                "expenses": ["read", "write"],
                "notifications": ["read"],
                "security": ["read", "write"],
            },
        },
    )
    assert role.status_code == 200, role.text

    u_east = await ac.post(
        "/api/v1/users",
        headers=headers,
        json={
            "email": "east@alpha.example.com",
            "full_name": "East Clerk",
            "password": "SecurePass123!",
            "role": "branch_clerk",
            "branch_id": b1_id,
        },
    )
    assert u_east.status_code == 200, u_east.text
    u_west = await ac.post(
        "/api/v1/users",
        headers=headers,
        json={
            "email": "west@alpha.example.com",
            "full_name": "West Clerk",
            "password": "SecurePass123!",
            "role": "branch_clerk",
            "branch_id": b2_id,
        },
    )
    assert u_west.status_code == 200, u_west.text

    await ensure_default_categories(db_session, seed["t1"].id)
    cats = (
        await db_session.execute(
            select(m.ExpenseCategory).where(m.ExpenseCategory.tenant_id == seed["t1"].id)
        )
    ).scalars().all()

    e_east = await create_expense(
        db_session,
        tenant_id=seed["t1"].id,
        user_id=u_east.json()["data"]["id"],
        amount=8,
        description="East branch expense",
        category_id=cats[0].id if cats else None,
        payment_method="cash",
    )
    e_west = await create_expense(
        db_session,
        tenant_id=seed["t1"].id,
        user_id=u_west.json()["data"]["id"],
        amount=9,
        description="West branch expense",
        category_id=cats[0].id if cats else None,
        payment_method="cash",
    )
    await db_session.commit()

    login = await ac.post(
        "/api/v1/auth/login",
        json={
            "email": "east@alpha.example.com",
            "password": "SecurePass123!",
            "tenant_id": "alpha",
        },
    )
    assert login.status_code == 200, login.text
    token = login.json()["data"]["access_token"]
    tenant_id = login.json()["data"]["user"]["tenant_id"]
    h = {"Authorization": f"Bearer {token}", "X-Tenant-ID": tenant_id}

    listed = await ac.get("/api/v1/expenses", headers=h)
    assert listed.status_code == 200, listed.text
    ids = {row["id"] for row in listed.json()["data"]}
    assert e_east.id in ids
    assert e_west.id not in ids
