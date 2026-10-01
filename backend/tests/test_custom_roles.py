"""Custom tenant roles (BR-3.2)."""

from __future__ import annotations

import pyotp
import pytest

from sqlalchemy import select

from app import models as m
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


@pytest.mark.asyncio
async def test_custom_role_permissions_persist_and_api_403(client, db_session):
    ac, seed = client
    admin = await _super(ac, seed)
    key = "pos_lead"
    created = await ac.post(
        "/api/v1/roles",
        headers=admin,
        json={
            "key": key,
            "label": "POS Lead",
            "permissions": {"dashboard": ["read"], "pos": ["read", "write"]},
        },
    )
    assert created.status_code == 200, created.text
    assert created.json()["data"]["permissions"]["pos"] == ["read", "write"]

    saved = await ac.patch(
        f"/api/v1/roles/{key}",
        headers=admin,
        json={"permissions": {"dashboard": ["read"], "pos": ["read", "write"], "inventory": ["read"]}},
    )
    assert saved.status_code == 200, saved.text
    assert "inventory" in saved.json()["data"]["permissions"]

    user = await ac.post(
        "/api/v1/users",
        headers=admin,
        json={
            "email": "poslead@alpha.example.com",
            "full_name": "POS Lead",
            "password": "SecurePass123!",
            "role": key,
        },
    )
    assert user.status_code == 200, user.text
    from sqlalchemy import select

    from app import models as m

    row = (
        await db_session.execute(select(m.User).where(m.User.email == "poslead@alpha.example.com"))
    ).scalar_one()
    row.email_verified = True
    await db_session.commit()

    login = await ac.post(
        "/api/v1/auth/login",
        json={
            "email": "poslead@alpha.example.com",
            "password": "SecurePass123!",
            "tenant_id": "alpha",
        },
    )
    assert login.status_code == 200, login.text
    headers = {
        "Authorization": f"Bearer {login.json()['data']['access_token']}",
        "X-Tenant-ID": seed["t1"].id,
    }
    pos_ok = await ac.get("/api/v1/pos/products/search", headers=headers, params={"q": "a"})
    assert pos_ok.status_code == 200, pos_ok.text
    inv_ok = await ac.get("/api/v1/products", headers=headers)
    assert inv_ok.status_code == 200, inv_ok.text

    stripped = await ac.patch(
        f"/api/v1/roles/{key}",
        headers=admin,
        json={"permissions": {"dashboard": ["read"], "pos": ["read", "write"]}},
    )
    assert stripped.status_code == 200, stripped.text
    inv_denied = await ac.get("/api/v1/products", headers=headers)
    assert inv_denied.status_code == 403, inv_denied.text
    pos_still = await ac.get("/api/v1/pos/products/search", headers=headers, params={"q": "a"})
    assert pos_still.status_code == 200, pos_still.text
    users_denied = await ac.get("/api/v1/users", headers=headers)
    assert users_denied.status_code == 403


def test_custom_role_soft_deactivate_ui_wired():
    from pathlib import Path

    users = (Path(__file__).resolve().parents[2] / "frontend/app/(dashboard)/users/page.tsx").read_text(
        encoding="utf-8"
    )
    assert "setCustomRoleActive" in users
    assert "include_inactive=true" in users
    assert "[inactive]" in users
    assert "Deactivate" in users
    assert "Activate" in users
    assert "assignableRoles" in users
    assert "Edit permissions" in users
    assert "saveCustomRolePerms" in users
    assert "CloneFromPicker" in users
    assert "No compatible roles available" in users
    assert "Create without cloning" in users
    assert "This company" in users
    assert "System templates" in users


async def _beta_hotel_admin(ac, db_session, seed):
    from app.rbac import permissions_for_role
    from app.security import hash_password
    from tests.conftest import set_tenant_industry

    await set_tenant_industry(db_session, seed["t2"], "hotel")
    existing = (
        await db_session.execute(select(m.User).where(m.User.email == "admin@beta.example.com"))
    ).scalar_one_or_none()
    if existing is None:
        db_session.add(
            m.User(
                tenant_id=seed["t2"].id,
                email="admin@beta.example.com",
                full_name="Beta Admin",
                password_hash=hash_password("SecurePass123!"),
                role="company_admin",
                email_verified=True,
                permissions=permissions_for_role("company_admin"),
            )
        )
        await db_session.commit()
    return await auth_headers(ac, email="admin@beta.example.com", tenant_slug="beta")


@pytest.mark.asyncio
async def test_clone_from_lists_are_industry_and_tenant_scoped(client, db_session):
    ac, seed = client
    retail = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    hotel = await _beta_hotel_admin(ac, db_session, seed)

    retail_role = await ac.post(
        "/api/v1/roles",
        headers=retail,
        json={
            "key": "alpha_floor",
            "label": "Alpha Floor",
            "permissions": {"dashboard": ["read"], "inventory": ["read", "write"]},
        },
    )
    assert retail_role.status_code == 200, retail_role.text
    alpha_id = retail_role.json()["data"]["id"]

    hotel_role = await ac.post(
        "/api/v1/roles",
        headers=hotel,
        json={
            "key": "beta_desk",
            "label": "Beta Desk",
            "base_role": "hotel_front_desk",
        },
    )
    assert hotel_role.status_code == 200, hotel_role.text
    beta_id = hotel_role.json()["data"]["id"]

    retail_keys = {r["role"] for r in (await ac.get("/api/v1/roles", headers=retail)).json()["data"]}
    hotel_keys = {r["role"] for r in (await ac.get("/api/v1/roles", headers=hotel)).json()["data"]}

    assert "cashier" in retail_keys
    assert "store_manager" in retail_keys
    assert "inventory_officer" in retail_keys
    assert "hotel_manager" not in retail_keys
    assert "hotel_front_desk" not in retail_keys
    assert "super_admin" not in retail_keys
    assert "platform_owner" not in retail_keys
    assert "alpha_floor" in retail_keys
    assert "beta_desk" not in retail_keys

    assert "hotel_manager" in hotel_keys
    assert "hotel_front_desk" in hotel_keys
    assert "cashier" in hotel_keys
    assert "store_manager" not in hotel_keys
    assert "platform_admin" not in hotel_keys
    assert "beta_desk" in hotel_keys
    assert "alpha_floor" not in hotel_keys

    spoof = await ac.get(f"/api/v1/roles/{alpha_id}", headers=hotel)
    assert spoof.status_code == 404, spoof.text
    spoof_patch = await ac.patch(
        f"/api/v1/roles/{alpha_id}",
        headers=hotel,
        json={"permissions": {"dashboard": ["read"]}},
    )
    assert spoof_patch.status_code == 404
    spoof_key = await ac.get("/api/v1/roles/alpha_floor", headers=hotel)
    assert spoof_key.status_code == 404
    hotel_as_retail = await ac.get("/api/v1/roles/hotel_manager", headers=retail)
    assert hotel_as_retail.status_code == 404
    store_as_hotel = await ac.get("/api/v1/roles/store_manager", headers=hotel)
    assert store_as_hotel.status_code == 404
    clone_denied = await ac.post(
        "/api/v1/roles",
        headers=retail,
        json={"key": "nope_hotel", "label": "Nope", "base_role": "hotel_manager"},
    )
    assert clone_denied.status_code == 404
    unknown = await ac.post(
        "/api/v1/roles",
        headers=retail,
        json={"key": "nope_unknown", "label": "Nope", "base_role": "garbage_xyz"},
    )
    assert unknown.status_code == 404
    platform = await ac.post(
        "/api/v1/roles",
        headers=retail,
        json={"key": "nope_plat", "label": "Nope", "base_role": "platform_owner"},
    )
    assert platform.status_code == 422

    cloned = await ac.post(
        "/api/v1/roles",
        headers=hotel,
        json={"key": "night_lead", "label": "Night Lead", "base_role": "hotel_front_desk"},
    )
    assert cloned.status_code == 200, cloned.text
    assert "hotel" in cloned.json()["data"]["permissions"]
    assert cloned.json()["data"]["permissions"] != {"*": ["*"]}

    edited = await ac.patch(
        "/api/v1/roles/night_lead",
        headers=hotel,
        json={"permissions": {"dashboard": ["read"], "hotel": ["read", "write"]}},
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["data"]["permissions"]["dashboard"] == ["read"]
    persisted = await ac.get("/api/v1/roles/night_lead", headers=hotel)
    assert persisted.status_code == 200
    assert persisted.json()["data"]["permissions"]["dashboard"] == ["read"]
    assert "hotel" in persisted.json()["data"]["permissions"]
    other_view = await ac.get(f"/api/v1/roles/{beta_id}", headers=retail)
    assert other_view.status_code == 404

    from app import audit as audit_svc

    await audit_svc.record_event(
        db_session,
        tenant_id=seed["t2"].id,
        user_id=seed["u2"].id,
        module="users",
        action="beta_clone_secret",
        entity="custom_role",
        entity_id=beta_id,
        details={"secret": "beta-only"},
    )
    await db_session.commit()
    audit = await ac.get(
        "/api/v1/audit-logs",
        headers=retail,
        params={"user_id": seed["u2"].id, "action": "beta_clone_secret"},
    )
    if audit.status_code == 200:
        actions = {row.get("action") for row in audit.json()["data"]}
        assert "beta_clone_secret" not in actions


@pytest.mark.asyncio
async def test_cloned_permissions_editable_and_persist(client):
    ac, seed = client
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    created = await ac.post(
        "/api/v1/roles",
        headers=admin,
        json={"key": "clone_cashier", "label": "Clone Cashier", "base_role": "cashier"},
    )
    assert created.status_code == 200, created.text
    perms = created.json()["data"]["permissions"]
    assert "pos" in perms
    assert "hotel" not in perms
    saved = await ac.patch(
        "/api/v1/roles/clone_cashier",
        headers=admin,
        json={"permissions": {"dashboard": ["read"], "pos": ["read", "write"], "inventory": ["read"]}},
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["data"]["permissions"]["inventory"] == ["read"]
    again = await ac.get("/api/v1/roles/clone_cashier", headers=admin)
    assert again.json()["data"]["permissions"]["inventory"] == ["read"]
    hotel_mod = await ac.patch(
        "/api/v1/roles/clone_cashier",
        headers=admin,
        json={"permissions": {"dashboard": ["read"], "hotel": ["read"]}},
    )
    assert hotel_mod.status_code == 422
