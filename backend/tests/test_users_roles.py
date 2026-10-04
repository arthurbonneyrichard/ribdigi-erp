"""Stage 1 — user lifecycle and roles catalog."""

from __future__ import annotations

import pyotp
import pytest

from app import models as m
from tests.conftest import auth_headers


async def _admin_headers(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_roles_catalog_lists_system_roles(client):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    r = await ac.get("/api/v1/roles", headers=headers)
    assert r.status_code == 200, r.text
    roles = {row["role"] for row in r.json()["data"]}
    assert "cashier" in roles
    assert "company_admin" in roles
    assert "super_admin" in roles
    detail = await ac.get("/api/v1/roles/cashier", headers=headers)
    assert detail.status_code == 200
    assert "pos" in detail.json()["data"]["permissions"]


@pytest.mark.asyncio
async def test_users_list_never_exposes_password_hash(client):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    r = await ac.get("/api/v1/users", headers=headers)
    assert r.status_code == 200, r.text
    rows = r.json()["data"]
    assert rows
    for row in rows:
        assert "password_hash" not in row
        assert "totp_secret_enc" not in row
        assert "email" in row
        assert "is_active" in row


@pytest.mark.asyncio
async def test_admin_creates_updates_and_deactivates_user(client):
    ac, seed = client
    headers = await _admin_headers(ac, seed)
    created = await ac.post(
        "/api/v1/users",
        headers=headers,
        json={
            "email": "newhire@alpha.example.com",
            "full_name": "New Hire",
            "password": "SecurePass123!",
            "role": "cashier",
        },
    )
    assert created.status_code == 200, created.text
    body = created.json()["data"]
    assert "password_hash" not in body.get("user", {})
    user_id = body["id"]

    patched = await ac.patch(
        f"/api/v1/users/{user_id}",
        headers=headers,
        json={"role": "sales_officer", "full_name": "New Hire Sales"},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["data"]["role"] == "sales_officer"
    assert patched.json()["data"]["full_name"] == "New Hire Sales"

    deactivated = await ac.delete(f"/api/v1/users/{user_id}", headers=headers)
    assert deactivated.status_code == 200, deactivated.text
    assert deactivated.json()["data"]["is_active"] is False

    denied = await ac.post(
        "/api/v1/auth/login",
        json={
            "email": "newhire@alpha.example.com",
            "password": "SecurePass123!",
            "tenant_id": "alpha",
        },
    )
    assert denied.status_code == 401

    reactivated = await ac.patch(
        f"/api/v1/users/{user_id}",
        headers=await _admin_headers(ac, seed),
        json={"is_active": True},
    )
    assert reactivated.status_code == 200
    assert reactivated.json()["data"]["is_active"] is True


@pytest.mark.asyncio
async def test_cashier_cannot_write_users(client):
    ac, seed = client
    headers = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    r = await ac.post(
        "/api/v1/users",
        headers=headers,
        json={
            "email": "x@alpha.example.com",
            "full_name": "Nope",
            "password": "SecurePass123!",
            "role": "cashier",
        },
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_cannot_deactivate_self(client):
    ac, seed = client
    headers = await _admin_headers(ac, seed)
    r = await ac.delete(f"/api/v1/users/{seed['super'].id}", headers=headers)
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_users_list_is_active_filter(client):
    ac, seed = client
    headers = await _admin_headers(ac, seed)
    created = await ac.post(
        "/api/v1/users",
        headers=headers,
        json={
            "email": "filter-demo@alpha.example.com",
            "full_name": "Filter Demo User",
            "password": "SecurePass123!",
            "role": "cashier",
        },
    )
    assert created.status_code == 200, created.text
    uid = created.json()["data"]["id"]

    await ac.delete(f"/api/v1/users/{uid}", headers=headers)

    all_rows = await ac.get("/api/v1/users", headers=headers)
    assert uid in {r["id"] for r in all_rows.json()["data"]}

    active_only = await ac.get("/api/v1/users?is_active=true", headers=headers)
    assert uid not in {r["id"] for r in active_only.json()["data"]}

    inactive_only = await ac.get("/api/v1/users?is_active=false", headers=headers)
    assert uid in {r["id"] for r in inactive_only.json()["data"]}
    assert all(r["is_active"] is False for r in inactive_only.json()["data"])


def test_user_status_filter_ui_wired():
    from pathlib import Path

    users = (
        Path(__file__).resolve().parents[2] / "frontend/app/(dashboard)/users/page.tsx"
    ).read_text(encoding="utf-8")
    assert "userManageFilter" in users
    assert 'aria-label="User status filter"' in users
    assert "managedUsers" in users
    assert "[inactive]" in users
    assert "setActive" in users


@pytest.mark.asyncio
async def test_foreign_user_get_404(client):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    r = await ac.get(f"/api/v1/users/{seed['u2'].id}", headers=headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_invalid_role_rejected(client):
    ac, seed = client
    headers = await _admin_headers(ac, seed)
    r = await ac.post(
        "/api/v1/users",
        headers=headers,
        json={
            "email": "badrole@alpha.example.com",
            "full_name": "Bad Role",
            "password": "SecurePass123!",
            "role": "not_a_role",
        },
    )
    assert r.status_code == 400


def test_user_management_create_button_wired_for_company_admin():
    from pathlib import Path

    from app.rbac import has_permission

    users = (
        Path(__file__).resolve().parents[2] / "frontend/app/(dashboard)/users/page.tsx"
    ).read_text(encoding="utf-8")
    shell = (
        Path(__file__).resolve().parents[2] / "frontend/components/Shell.tsx"
    ).read_text(encoding="utf-8")
    company = (
        Path(__file__).resolve().parents[2] / "frontend/app/(dashboard)/company/page.tsx"
    ).read_text(encoding="utf-8")
    css = (
        Path(__file__).resolve().parents[2] / "frontend/app/globals.css"
    ).read_text(encoding="utf-8")
    assert "canWriteUsers" in users
    assert "USER_ADMIN_ROLES" in users
    assert "company_admin" in users
    assert 'aria-label="Add User"' in users
    assert 'id="create-user"' in users
    assert 'aria-label="Create user"' in users
    assert "users:write" in users
    assert "users-perm-msg" in users
    assert "users-page-head" in users
    assert "users-add-btn" in css
    assert "@media(max-width:720px)" in css
    assert "['dashboard', 'notifications', 'security', 'users']" in shell
    assert 'href="/users#create-user"' in company
    assert has_permission("company_admin", "users", "write")
    assert has_permission(
        "cashier",
        "users",
        "write",
        overrides={"users": ["create"]},
    )
    assert not has_permission("cashier", "users", "write")
    assert not has_permission("store_manager", "users", "write")


@pytest.mark.asyncio
async def test_company_admin_creates_user_and_duplicate_email_409(client):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    payload = {
        "email": "hire-ca@alpha.example.com",
        "full_name": "Company Hire",
        "password": "SecurePass123!",
        "role": "cashier",
    }
    created = await ac.post("/api/v1/users", headers=headers, json=payload)
    assert created.status_code == 200, created.text
    uid = created.json()["data"]["id"]
    assert created.json()["data"]["user"]["role"] == "cashier"

    dup = await ac.post("/api/v1/users", headers=headers, json=payload)
    assert dup.status_code == 409

    listed = await ac.get("/api/v1/users", headers=headers)
    assert listed.status_code == 200
    emails = {row["email"] for row in listed.json()["data"]}
    assert "hire-ca@alpha.example.com" in emails
    assert "super@alpha.example.com" not in emails
    ids = {row["id"] for row in listed.json()["data"]}
    assert seed["super"].id not in ids
    assert uid in ids

    hidden = await ac.get(f"/api/v1/users/{seed['super'].id}", headers=headers)
    assert hidden.status_code == 404

    invited = await ac.post(f"/api/v1/users/{uid}/confirm-email", headers=headers)
    assert invited.status_code == 200, invited.text
    assert invited.json()["data"]["email_verified"] is True


@pytest.mark.asyncio
async def test_tenant_admin_like_company_admin_stays_in_own_tenant(client):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    r = await ac.get(f"/api/v1/users/{seed['u2'].id}", headers=headers)
    assert r.status_code == 404
    patched = await ac.patch(
        f"/api/v1/users/{seed['u2'].id}",
        headers=headers,
        json={"full_name": "Should Not Work"},
    )
    assert patched.status_code == 404


@pytest.mark.asyncio
async def test_cashier_users_api_forbidden_same_as_ui(client):
    ac, seed = client
    headers = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    listed = await ac.get("/api/v1/users", headers=headers)
    assert listed.status_code == 403
    created = await ac.post(
        "/api/v1/users",
        headers=headers,
        json={
            "email": "bypass@alpha.example.com",
            "full_name": "Bypass",
            "password": "SecurePass123!",
            "role": "cashier",
        },
    )
    assert created.status_code == 403


@pytest.mark.asyncio
async def test_store_manager_can_read_users_not_write(client):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    listed = await ac.get("/api/v1/users", headers=headers)
    assert listed.status_code == 200
    created = await ac.post(
        "/api/v1/users",
        headers=headers,
        json={
            "email": "mgr-hire@alpha.example.com",
            "full_name": "Mgr Hire",
            "password": "SecurePass123!",
            "role": "cashier",
        },
    )
    assert created.status_code == 403


@pytest.mark.asyncio
async def test_users_module_always_on_when_package_stripped(client, db_session):
    ac, seed = client
    from app import tenants as tenants_svc

    tenant = await tenants_svc.get_tenant(db_session, seed["t1"].id)
    await tenants_svc.set_enabled_modules(
        db_session,
        tenant,
        ["dashboard", "inventory", "notifications", "security"],
        commit=True,
    )
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    listed = await ac.get("/api/v1/users", headers=headers)
    assert listed.status_code == 200, listed.text
    me = await ac.get("/api/v1/me", headers=headers)
    assert "users" in me.json()["data"]["enabled_modules"]
