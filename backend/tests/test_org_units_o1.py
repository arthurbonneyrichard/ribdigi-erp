"""Stage 21 O1: Org units fidelity (BR-2.2–2.5)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_branch_store_warehouse_department_fidelity(client):
    """BR-2.2–2.5: CRUD attrs, links, soft-deactivate without data loss."""
    ac, seed = client
    headers = await _super(ac, seed)
    mgr_id = seed["mgr1"].id

    branch = await ac.post(
        "/api/v1/branches",
        headers=headers,
        json={
            "code": "O1BR",
            "name": "O1 Branch",
            "address": "12 Independence Ave",
            "phone": "+233200001111",
            "email": "o1branch@alpha.example.com",
            "manager_id": mgr_id,
        },
    )
    assert branch.status_code == 200, branch.text
    b = branch.json()["data"]
    branch_id = b["id"]
    assert b["code"] == "O1BR"
    assert b["manager_id"] == mgr_id
    assert b["address"] == "12 Independence Ave"
    assert b["phone"] == "+233200001111"
    assert b["email"] == "o1branch@alpha.example.com"
    assert b["is_active"] is True

    hours = {"mon": "09:00-17:00", "tue": "09:00-17:00", "closed": ["sun"]}
    store = await ac.post(
        "/api/v1/stores",
        headers=headers,
        json={
            "code": "O1ST",
            "name": "O1 Retail Store",
            "address": "Mall Unit 4",
            "phone": "+233200002222",
            "manager_id": mgr_id,
            "branch_id": branch_id,
            "operating_hours": hours,
        },
    )
    assert store.status_code == 200, store.text
    s = store.json()["data"]
    store_id = s["id"]
    assert s["branch_id"] == branch_id
    assert s["manager_id"] == mgr_id
    assert s["operating_hours"] == hours
    assert s["warehouse_id"]
    linked_wh_id = s["warehouse_id"]
    assert s["warehouse_code"] == "WH-O1ST"

    warehouse = await ac.post(
        "/api/v1/warehouses",
        headers=headers,
        json={
            "code": "O1COLD",
            "name": "O1 Cold Storage",
            "warehouse_type": "cold",
            "manager_id": mgr_id,
            "address": "Cold chain bay 2",
            "capacity": 5000,
        },
    )
    assert warehouse.status_code == 200, warehouse.text
    w = warehouse.json()["data"]
    warehouse_id = w["id"]
    assert w["warehouse_type"] == "cold"
    assert w["manager_id"] == mgr_id
    assert w["address"] == "Cold chain bay 2"
    assert float(w["capacity"]) == 5000.0
    assert w["is_active"] is True

    listed_wh = await ac.get("/api/v1/warehouses", headers=headers)
    assert listed_wh.status_code == 200, listed_wh.text
    wh_ids = {row["id"] for row in listed_wh.json()["data"]}
    assert linked_wh_id in wh_ids
    assert warehouse_id in wh_ids

    dept = await ac.post(
        "/api/v1/departments",
        headers=headers,
        json={
            "code": "O1OPS",
            "name": "O1 Operations",
            "branch_id": branch_id,
            "head_user_id": mgr_id,
        },
    )
    assert dept.status_code == 200, dept.text
    d = dept.json()["data"]
    dept_id = d["id"]
    assert d["head_user_id"] == mgr_id
    assert d["branch_id"] == branch_id

    # Department-based reporting filter while department is active
    expense = await ac.post(
        "/api/v1/expenses",
        headers=headers,
        json={
            "category": "General",
            "amount": 25,
            "description": "O1 dept filter",
            "payment_method": "cash",
            "department_id": dept_id,
        },
    )
    assert expense.status_code == 200, expense.text
    expense_id = expense.json()["data"]["id"]
    assert expense.json()["data"]["department_id"] == dept_id

    filtered = await ac.get(
        "/api/v1/expenses",
        headers=headers,
        params={"department_id": dept_id},
    )
    assert filtered.status_code == 200, filtered.text
    assert any(r["id"] == expense_id for r in filtered.json()["data"])

    # Soft-deactivate without hard delete / data loss (ADR-003)
    for path, body in (
        (f"/api/v1/branches/{branch_id}", {"name": "O1 Branch Renamed", "is_active": False}),
        (f"/api/v1/stores/{store_id}", {"is_active": False}),
        (f"/api/v1/warehouses/{warehouse_id}", {"is_active": False, "capacity": 4800}),
        (f"/api/v1/departments/{dept_id}", {"is_active": False}),
    ):
        resp = await ac.patch(path, headers=headers, json=body)
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["is_active"] is False

    branches = await ac.get("/api/v1/branches", headers=headers)
    assert branches.status_code == 200
    brow = next(r for r in branches.json()["data"] if r["id"] == branch_id)
    assert brow["name"] == "O1 Branch Renamed"
    assert brow["is_active"] is False
    assert brow["manager_id"] == mgr_id
    assert brow["address"] == "12 Independence Ave"

    stores = await ac.get("/api/v1/stores", headers=headers)
    assert stores.status_code == 200
    srow = next(r for r in stores.json()["data"] if r["id"] == store_id)
    assert srow["is_active"] is False
    assert srow["branch_id"] == branch_id
    assert srow["warehouse_id"] == linked_wh_id
    assert srow["operating_hours"] == hours

    warehouses = await ac.get("/api/v1/warehouses", headers=headers)
    wrow = next(r for r in warehouses.json()["data"] if r["id"] == warehouse_id)
    assert wrow["is_active"] is False
    assert wrow["warehouse_type"] == "cold"
    assert float(wrow["capacity"]) == 4800.0

    deps = await ac.get("/api/v1/departments", headers=headers)
    drow = next(r for r in deps.json()["data"] if r["id"] == dept_id)
    assert drow["is_active"] is False
    assert drow["head_user_id"] == mgr_id

    # Historical expense remains filterable after department soft-deactivate
    still = await ac.get(
        "/api/v1/expenses",
        headers=headers,
        params={"department_id": dept_id},
    )
    assert still.status_code == 200, still.text
    assert any(r["id"] == expense_id for r in still.json()["data"])


def test_br_2_2_to_2_5_and_plan_synced():
    br = (ROOT / "docs" / "BUSINESS_REQUIREMENTS_DOCUMENT.md").read_text(encoding="utf-8")
    s22 = br.split("#### BR-2.2 Branch Management")[1].split("#### BR-2.3")[0]
    assert "[x] Create/edit/delete branches" in s22
    assert "[x] Assign branch code and manager" in s22
    assert "[x] Branch-specific address and contact" in s22
    assert "[x] Deactivate branch without data loss" in s22
    assert "Stage 21 O1" in s22
    assert "test_org_units_o1.py" in s22

    s23 = br.split("#### BR-2.3 Store Management")[1].split("#### BR-2.4")[0]
    assert "[x] Create stores with name, code, location" in s23
    assert "[x] Assign store manager" in s23
    assert "[x] Configure store operating hours" in s23
    assert "[x] Link store to branch and warehouse" in s23
    assert "Stage 21 O1" in s23

    s24 = br.split("#### BR-2.4 Warehouse Setup")[1].split("#### BR-2.5")[0]
    assert "[x] Create multiple warehouses" in s24
    assert "[x] Define warehouse type" in s24
    assert "[x] Assign warehouse manager" in s24
    assert "[x] Configure warehouse address and capacity" in s24
    assert "Stage 21 O1" in s24

    s25 = br.split("#### BR-2.5 Department Setup")[1].split("#### BR-2.6")[0]
    assert "[x] Create departments" in s25
    assert "[x] Assign department head" in s25
    assert "[x] Department-based reporting filters" in s25
    assert "Stage 21 O1" in s25

    plan = (ROOT / "docs" / "STAGE_21_PLAN.md").read_text(encoding="utf-8")
    o1_line = [ln for ln in plan.splitlines() if "| **O1**" in ln][0]
    assert "COMPLETE" in o1_line
    assert "test_org_units_o1.py" in plan
