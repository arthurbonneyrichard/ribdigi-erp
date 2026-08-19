"""Stage 21 U1: Users & roles fidelity (BR-3)."""

from __future__ import annotations

import io
from pathlib import Path

import pyotp
import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]

SYSTEM_ROLES = {
    "super_admin",
    "company_admin",
    "store_manager",
    "sales_officer",
    "inventory_officer",
    "accountant",
    "cashier",
}


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_users_roles_fidelity(client):
    """BR-3.1–3.3: CRUD/import, system+custom roles, inheritance/record_scope override."""
    ac, seed = client
    headers = await _super(ac, seed)

    # --- BR-3.2 predefined roles + default permission sets ---
    catalog = await ac.get("/api/v1/roles", headers=headers)
    assert catalog.status_code == 200, catalog.text
    roles = {r["role"]: r for r in catalog.json()["data"]}
    assert SYSTEM_ROLES.issubset(roles.keys())
    for slug in SYSTEM_ROLES:
        assert roles[slug]["system"] is True
        assert roles[slug]["permissions"]
        assert roles[slug]["label"]
        assert roles[slug]["record_scope"] in {"own", "department", "branch", "all"}

    cashier = await ac.get("/api/v1/roles/cashier", headers=headers)
    assert cashier.status_code == 200, cashier.text
    assert "pos" in cashier.json()["data"]["permissions"]

    # Org assignment targets (branch/dept; store membership deferred ADR-005)
    branch = await ac.post(
        "/api/v1/branches",
        headers=headers,
        json={"code": "U1BR", "name": "U1 Branch"},
    )
    assert branch.status_code == 200, branch.text
    branch_id = branch.json()["data"]["id"]
    dept = await ac.post(
        "/api/v1/departments",
        headers=headers,
        json={"code": "U1DE", "name": "U1 Dept", "branch_id": branch_id},
    )
    assert dept.status_code == 200, dept.text
    dept_id = dept.json()["data"]["id"]

    # --- BR-3.2 custom role (inherits base_role permissions, then override map) ---
    custom = await ac.post(
        "/api/v1/roles",
        headers=headers,
        json={
            "slug": "u1_floor",
            "label": "U1 Floor Lead",
            "base_role": "cashier",
            "record_scope": "own",
            "permissions": {
                "dashboard": ["read"],
                "pos": ["read", "write"],
                "inventory": ["read"],
                "notifications": ["read", "write"],
                "security": ["read", "write"],
            },
        },
    )
    assert custom.status_code == 200, custom.text
    assert custom.json()["data"]["system"] is False
    assert custom.json()["data"]["permissions"]["pos"] == ["read", "write"]

    perms = await ac.put(
        "/api/v1/roles/u1_floor/permissions",
        headers=headers,
        json={
            "permissions": {
                "dashboard": ["read"],
                "pos": ["read", "write"],
                "inventory": ["read", "write"],
                "notifications": ["read", "write"],
                "security": ["read", "write"],
            },
            "record_scope": "branch",
        },
    )
    assert perms.status_code == 200, perms.text
    assert perms.json()["data"]["permissions"]["inventory"] == ["read", "write"]
    assert perms.json()["data"]["record_scope"] == "branch"

    # --- BR-3.1 create / edit / soft deactivate / activate ---
    created = await ac.post(
        "/api/v1/users",
        headers=headers,
        json={
            "email": "u1.hire@alpha.example.com",
            "full_name": "U1 Hire",
            "password": "SecurePass123!",
            "role": "u1_floor",
            "phone": "+233200001001",
            "branch_id": branch_id,
            "department_id": dept_id,
            "record_scope": "own",
        },
    )
    assert created.status_code == 200, created.text
    body = created.json()["data"]
    user_id = body["id"]
    user = body["user"]
    assert user["role"] == "u1_floor"
    assert user["phone"] == "+233200001001"
    assert user["branch_id"] == branch_id
    assert user["department_id"] == dept_id
    assert user["is_active"] is True
    # Role permissions inherited onto user snapshot
    assert "pos" in (user.get("permissions") or {})
    assert user.get("record_scope") == "own"
    assert "password_hash" not in user

    # User-level record_scope override (module map stays role-driven)
    patched = await ac.patch(
        f"/api/v1/users/{user_id}",
        headers=headers,
        json={
            "full_name": "U1 Hire Sales",
            "phone": "+233200001002",
            "role": "sales_officer",
            "record_scope": "department",
        },
    )
    assert patched.status_code == 200, patched.text
    pdata = patched.json()["data"]
    assert pdata["full_name"] == "U1 Hire Sales"
    assert pdata["phone"] == "+233200001002"
    assert pdata["role"] == "sales_officer"
    assert pdata.get("record_scope") == "department"

    deactivated = await ac.delete(f"/api/v1/users/{user_id}", headers=headers)
    assert deactivated.status_code == 200, deactivated.text
    assert deactivated.json()["data"]["is_active"] is False

    got = await ac.get(f"/api/v1/users/{user_id}", headers=await _super(ac, seed))
    assert got.status_code == 200, got.text
    assert got.json()["data"]["is_active"] is False
    assert got.json()["data"]["email"] == "u1.hire@alpha.example.com"

    reactivated = await ac.patch(
        f"/api/v1/users/{user_id}",
        headers=await _super(ac, seed),
        json={"is_active": True},
    )
    assert reactivated.status_code == 200, reactivated.text
    assert reactivated.json()["data"]["is_active"] is True

    # --- BR-3.1 CSV bulk import ---
    tmpl = await ac.get("/api/v1/users/import/template", headers=await _super(ac, seed))
    assert tmpl.status_code == 200, tmpl.text
    assert "full_name,email" in tmpl.text

    csv_body = (
        "full_name,email,phone,role,branch_code,department_code,password,record_scope\n"
        "U1 Import,u1.import@alpha.example.com,,cashier,,,SecurePass123!,own\n"
    )
    imported = await ac.post(
        "/api/v1/users/import?dry_run=false",
        headers=await _super(ac, seed),
        files={"file": ("users.csv", io.BytesIO(csv_body.encode()), "text/csv")},
    )
    assert imported.status_code == 200, imported.text
    assert imported.json()["data"]["valid_rows"] == 1
    assert any(
        row["email"] == "u1.import@alpha.example.com"
        for row in imported.json()["data"]["created"]
    )


def test_br_3_and_plan_synced():
    br = (ROOT / "docs" / "BUSINESS_REQUIREMENTS_DOCUMENT.md").read_text(encoding="utf-8")
    s31 = br.split("#### BR-3.1 User Account CRUD")[1].split("#### BR-3.2")[0]
    assert "[x] Create user with name, email, phone, role, branch/store assignment" in s31
    assert "[x] Edit user details and assignments" in s31
    assert "[x] Soft delete (deactivate) user" in s31
    assert "ADR_003" in s31 or "ADR-003" in s31
    assert "[x] Activate/deactivate toggle" in s31
    assert "[x] Bulk user import via CSV" in s31
    assert "Stage 21 U1" in s31
    assert "test_users_roles_u1.py" in s31
    assert "ADR_005" in s31 or "ADR-005" in s31

    s32 = br.split("#### BR-3.2 Role Management")[1].split("#### BR-3.3")[0]
    assert "[x] Predefined roles" in s32
    assert "[x] Each role has default permission set" in s32
    assert "[x] Custom role creation capability" in s32
    assert "[x] Role assignment to users" in s32
    assert "Stage 21 U1" in s32

    s33 = br.split("#### BR-3.3 Permission System")[1].split("---")[0]
    assert "[x] **Module Permissions:**" in s33
    assert "[x] **Menu Permissions:**" in s33
    assert "[x] **Record Permissions:**" in s33
    assert "[x] Permission inheritance from role" in s33
    assert "Stage 21 U1" in s33
    assert "record_scope" in s33

    plan = (ROOT / "docs" / "STAGE_21_PLAN.md").read_text(encoding="utf-8")
    u1_line = [ln for ln in plan.splitlines() if "| **U1**" in ln][0]
    assert "COMPLETE" in u1_line
    assert "test_users_roles_u1.py" in plan
