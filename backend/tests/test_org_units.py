"""Stage 1 org units: branches, departments, department record scope."""

from __future__ import annotations

import pyotp
import pytest

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

    await ac.post(
        "/api/v1/roles",
        headers=headers,
        json={
            "slug": "dept_clerk",
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
            "record_scope": "department",
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
            "record_scope": "department",
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
            "record_scope": "department",
        },
    )
    assert u3.status_code == 200, u3.text

    from sqlalchemy import select

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

    await ac.post(
        "/api/v1/roles",
        headers=headers,
        json={
            "slug": "branch_clerk",
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

    u_east = await ac.post(
        "/api/v1/users",
        headers=headers,
        json={
            "email": "east@alpha.example.com",
            "full_name": "East Clerk",
            "password": "SecurePass123!",
            "role": "branch_clerk",
            "branch_id": b1_id,
            "record_scope": "branch",
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
            "record_scope": "branch",
        },
    )
    assert u_west.status_code == 200, u_west.text

    from sqlalchemy import select

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


@pytest.mark.asyncio
async def test_dashboard_includes_stage1_kpis(client):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    r = await ac.get("/api/v1/dashboard", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    for key in (
        "total_sales",
        "customers",
        "suppliers",
        "daily_revenue",
        "monthly_revenue",
        "recent_sales",
        "top_products",
        "out_of_stock",
        "expiring_batches",
        "prior_month_revenue",
        "mom_change_pct",
    ):
        assert key in data


@pytest.mark.asyncio
async def test_org_admin_fields_store_warehouse_and_plan(client):
    ac, seed = client
    headers = await _admin_headers(ac, seed)

    branch = await ac.post(
        "/api/v1/branches",
        headers=headers,
        json={
            "code": "EAST",
            "name": "East Branch",
            "phone": "+233200000001",
            "email": "east@alpha.example.com",
        },
    )
    assert branch.status_code == 200, branch.text
    assert branch.json()["data"]["phone"] == "+233200000001"
    branch_id = branch.json()["data"]["id"]

    patched_branch = await ac.patch(
        f"/api/v1/branches/{branch_id}",
        headers=headers,
        json={"phone": "+233200000099"},
    )
    assert patched_branch.status_code == 200, patched_branch.text
    assert patched_branch.json()["data"]["phone"] == "+233200000099"

    store = await ac.post(
        "/api/v1/stores",
        headers=headers,
        json={
            "code": "ST-EAST",
            "name": "East Store",
            "phone": "+233200000010",
            "branch_id": branch_id,
            "operating_hours": {"mon": "08:00-18:00"},
        },
    )
    assert store.status_code == 200, store.text
    store_id = store.json()["data"]["id"]
    assert store.json()["data"]["operating_hours"]["mon"] == "08:00-18:00"

    store_upd = await ac.patch(
        f"/api/v1/stores/{store_id}",
        headers=headers,
        json={"phone": "+233200000011", "operating_hours": {"tue": "09:00-17:00"}},
    )
    assert store_upd.status_code == 200, store_upd.text
    assert store_upd.json()["data"]["phone"] == "+233200000011"
    assert store_upd.json()["data"]["operating_hours"]["tue"] == "09:00-17:00"

    wh = await ac.post(
        "/api/v1/warehouses",
        headers=headers,
        json={
            "code": "WH-COLD",
            "name": "Cold Room",
            "warehouse_type": "cold",
            "address": "Dock 2",
            "capacity": 1000,
            "store_id": store_id,
        },
    )
    assert wh.status_code == 200, wh.text
    assert wh.json()["data"]["warehouse_type"] == "cold"
    wh_id = wh.json()["data"]["id"]

    wh_upd = await ac.patch(
        f"/api/v1/warehouses/{wh_id}",
        headers=headers,
        json={"capacity": 1500, "is_active": True},
    )
    assert wh_upd.status_code == 200, wh_upd.text
    assert float(wh_upd.json()["data"]["capacity"]) == 1500

    listed = await ac.get("/api/v1/warehouses", headers=headers)
    assert listed.status_code == 200, listed.text
    assert all(isinstance(row, dict) and "warehouse_type" in row for row in listed.json()["data"])

    profile = await ac.patch(
        "/api/v1/tenants/me",
        headers=headers,
        json={
            "plan_code": "growth",
            "legal_name": "Alpha Retail Ltd",
            "registration_number": "CS123456",
            "billing_address": "Billing Rd 1",
            "shipping_address": "Ship Rd 2",
            "warehouse_address": "Wh Rd 3",
            "contact_person_name": "Ada Admin",
            "contact_person_email": "ada@alpha.example.com",
            "contact_person_phone": "+233200000020",
            "inactivity_timeout_minutes": 45,
        },
    )
    assert profile.status_code == 200, profile.text
    pdata = profile.json()["data"]
    assert pdata["plan_code"] == "growth"
    assert pdata["legal_name"] == "Alpha Retail Ltd"
    assert pdata["inactivity_timeout_minutes"] == 45

    me = await ac.get("/api/v1/me", headers=headers)
    assert me.status_code == 200, me.text
    assert me.json()["data"]["inactivity_timeout_minutes"] == 45
