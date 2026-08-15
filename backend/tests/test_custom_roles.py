"""Custom tenant roles (BR-3.2)."""

from __future__ import annotations

import pyotp
import pytest

from app.rbac import has_permission, is_system_role
from tests.conftest import auth_headers


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


def test_has_permission_custom_role_does_not_merge_cashier():
    assert not is_system_role("warehouse_lead")
    # Only inventory — must not inherit cashier POS
    assert has_permission(
        "warehouse_lead",
        "inventory",
        "write",
        overrides={"inventory": ["read", "write"]},
    )
    assert not has_permission(
        "warehouse_lead",
        "pos",
        "write",
        overrides={"inventory": ["read", "write"]},
    )


@pytest.mark.asyncio
async def test_create_assign_and_enforce_custom_role(client, db_session):
    ac, seed = client
    admin = await _super(ac, seed)

    created = await ac.post(
        "/api/v1/roles",
        headers=admin,
        json={
            "key": "warehouse_lead",
            "label": "Warehouse Lead",
            "base_role": "inventory_officer",
            "record_scope": "all",
        },
    )
    assert created.status_code == 200, created.text
    body = created.json()["data"]
    assert body["role"] == "warehouse_lead"
    assert body["system"] is False
    assert "inventory" in body["permissions"]
    assert body["record_scope"] == "all"

    catalog = await ac.get("/api/v1/roles", headers=admin)
    keys = {r["role"] for r in catalog.json()["data"]}
    assert "warehouse_lead" in keys
    assert "cashier" in keys

    user = await ac.post(
        "/api/v1/users",
        headers=admin,
        json={
            "email": "whlead@alpha.example.com",
            "full_name": "Warehouse Lead",
            "password": "SecurePass123!",
            "role": "warehouse_lead",
        },
    )
    assert user.status_code == 200, user.text
    assert user.json()["data"]["user"]["role"] == "warehouse_lead"

    # Admin-created users start unverified; mark verified so login exercises RBAC.
    from sqlalchemy import select

    from app import models as m

    row = (
        await db_session.execute(
            select(m.User).where(m.User.email == "whlead@alpha.example.com")
        )
    ).scalar_one()
    row.email_verified = True
    await db_session.commit()

    login = await ac.post(
        "/api/v1/auth/login",
        json={
            "email": "whlead@alpha.example.com",
            "password": "SecurePass123!",
            "tenant_id": "alpha",
        },
    )
    assert login.status_code == 200, login.text
    token = login.json()["data"]["access_token"]
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": seed["t1"].id,
    }

    # inventory:read allowed via cloned inventory_officer map
    inv = await ac.get("/api/v1/products", headers=headers)
    assert inv.status_code == 200, inv.text

    # users:write should be denied (inventory_officer lacks users write)
    denied = await ac.post(
        "/api/v1/users",
        headers=headers,
        json={
            "email": "x@alpha.example.com",
            "full_name": "Nope",
            "password": "SecurePass123!",
            "role": "cashier",
        },
    )
    assert denied.status_code == 403


@pytest.mark.asyncio
async def test_cannot_delete_custom_role_with_users(client):
    ac, seed = client
    admin = await _super(ac, seed)
    await ac.post(
        "/api/v1/roles",
        headers=admin,
        json={
            "key": "buyer",
            "label": "Buyer",
            "permissions": {"purchasing": ["read", "write"], "dashboard": ["read"]},
        },
    )
    await ac.post(
        "/api/v1/users",
        headers=admin,
        json={
            "email": "buyer@alpha.example.com",
            "full_name": "Buyer",
            "password": "SecurePass123!",
            "role": "buyer",
        },
    )
    blocked = await ac.delete("/api/v1/roles/buyer", headers=admin)
    assert blocked.status_code == 409

    # Deactivate user then delete role still blocked while assigned
    users = await ac.get("/api/v1/users", headers=admin)
    uid = next(u["id"] for u in users.json()["data"] if u["email"] == "buyer@alpha.example.com")
    await ac.patch(f"/api/v1/users/{uid}", headers=admin, json={"role": "cashier"})
    deleted = await ac.delete("/api/v1/roles/buyer", headers=admin)
    assert deleted.status_code == 200, deleted.text


@pytest.mark.asyncio
async def test_system_roles_immutable(client):
    ac, seed = client
    admin = await _super(ac, seed)
    bad = await ac.patch(
        "/api/v1/roles/cashier",
        headers=admin,
        json={"label": "Nope"},
    )
    assert bad.status_code == 400
    collide = await ac.post(
        "/api/v1/roles",
        headers=admin,
        json={"key": "cashier", "label": "Clone", "base_role": "cashier"},
    )
    assert collide.status_code == 400


@pytest.mark.asyncio
async def test_custom_role_soft_deactivate_and_reactivate(client):
    """BR-3.2 — PATCH is_active; default catalog hides inactive; include_inactive lists them;
    new assignment of inactive roles is blocked; reactivation restores catalog + assign."""
    ac, seed = client
    admin = await _super(ac, seed)
    key = "night_auditor"

    created = await ac.post(
        "/api/v1/roles",
        headers=admin,
        json={
            "key": key,
            "label": "Night Auditor",
            "base_role": "accountant",
            "record_scope": "branch",
        },
    )
    assert created.status_code == 200, created.text
    assert created.json()["data"]["is_active"] is True

    deact = await ac.patch(
        f"/api/v1/roles/{key}",
        headers=admin,
        json={"is_active": False},
    )
    assert deact.status_code == 200, deact.text
    assert deact.json()["data"]["is_active"] is False

    default_catalog = await ac.get("/api/v1/roles", headers=admin)
    assert default_catalog.status_code == 200
    default_keys = {r["role"] for r in default_catalog.json()["data"]}
    assert key not in default_keys
    assert "cashier" in default_keys

    full = await ac.get("/api/v1/roles?include_inactive=true", headers=admin)
    assert full.status_code == 200
    by_role = {r["role"]: r for r in full.json()["data"]}
    assert key in by_role
    assert by_role[key]["is_active"] is False
    assert by_role[key]["system"] is False

    blocked = await ac.post(
        "/api/v1/users",
        headers=admin,
        json={
            "email": "night@alpha.example.com",
            "full_name": "Night User",
            "password": "SecurePass123!",
            "role": key,
        },
    )
    assert blocked.status_code == 400, blocked.text

    react = await ac.patch(
        f"/api/v1/roles/{key}",
        headers=admin,
        json={"is_active": True},
    )
    assert react.status_code == 200, react.text
    assert react.json()["data"]["is_active"] is True

    restored = await ac.get("/api/v1/roles", headers=admin)
    assert key in {r["role"] for r in restored.json()["data"]}

    user = await ac.post(
        "/api/v1/users",
        headers=admin,
        json={
            "email": "night@alpha.example.com",
            "full_name": "Night User",
            "password": "SecurePass123!",
            "role": key,
        },
    )
    assert user.status_code == 200, user.text
    assert user.json()["data"]["user"]["role"] == key


def test_custom_role_soft_deactivate_ui_wired():
    from pathlib import Path

    users = (Path(__file__).resolve().parents[2] / "frontend/app/users/page.tsx").read_text(
        encoding="utf-8"
    )
    assert "setCustomRoleActive" in users
    assert "include_inactive=true" in users
    assert "[inactive]" in users
    assert "Deactivate" in users
    assert "Activate" in users
    assert "assignableRoles" in users
