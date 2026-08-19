"""Custom tenant roles — create, assign, authorize, delete guards."""

from __future__ import annotations

import pyotp
import pytest

from app import models as m
from app.rbac import has_permission
from tests.conftest import auth_headers


async def _admin_headers(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_create_custom_role_appears_in_catalog(client):
    ac, seed = client
    headers = await _admin_headers(ac, seed)
    created = await ac.post(
        "/api/v1/roles",
        headers=headers,
        json={
            "slug": "floor_lead",
            "label": "Floor Lead",
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
    assert created.status_code == 200, created.text
    body = created.json()["data"]
    assert body["role"] == "floor_lead"
    assert body["system"] is False
    assert body["permissions"]["pos"] == ["read", "write"]
    assert "*" not in body["permissions"]

    catalog = await ac.get("/api/v1/roles", headers=headers)
    assert catalog.status_code == 200
    roles = {r["role"]: r for r in catalog.json()["data"]}
    assert "floor_lead" in roles
    assert roles["cashier"]["system"] is True
    assert roles["floor_lead"]["system"] is False


@pytest.mark.asyncio
async def test_cannot_create_system_slug_or_wildcard_custom_role(client):
    ac, seed = client
    headers = await _admin_headers(ac, seed)
    reserved = await ac.post(
        "/api/v1/roles",
        headers=headers,
        json={"slug": "cashier", "label": "Fake Cashier", "base_role": "cashier"},
    )
    assert reserved.status_code == 400

    wildcard = await ac.post(
        "/api/v1/roles",
        headers=headers,
        json={
            "slug": "almost_admin",
            "label": "Almost Admin",
            "permissions": {"*": ["*"]},
        },
    )
    assert wildcard.status_code == 400


@pytest.mark.asyncio
async def test_assign_custom_role_enforces_permissions(client):
    ac, seed = client
    headers = await _admin_headers(ac, seed)
    await ac.post(
        "/api/v1/roles",
        headers=headers,
        json={
            "slug": "pos_only",
            "label": "POS Only",
            "permissions": {
                "dashboard": ["read"],
                "pos": ["read", "write"],
                "notifications": ["read"],
                "security": ["read", "write"],
            },
            "record_scope": "own",
        },
    )
    created = await ac.post(
        "/api/v1/users",
        headers=headers,
        json={
            "email": "posonly@alpha.example.com",
            "full_name": "POS Only User",
            "password": "SecurePass123!",
            "role": "pos_only",
        },
    )
    assert created.status_code == 200, created.text
    assert created.json()["data"]["user"]["role"] == "pos_only"

    login = await ac.post(
        "/api/v1/auth/login",
        json={
            "email": "posonly@alpha.example.com",
            "password": "SecurePass123!",
            "tenant_id": "alpha",
        },
    )
    assert login.status_code == 200, login.text
    token = login.json()["data"]["access_token"]
    tenant_id = login.json()["data"]["user"]["tenant_id"]
    user_headers = {"Authorization": f"Bearer {token}", "X-Tenant-ID": tenant_id}

    pos_ok = await ac.get("/api/v1/pos/sessions", headers=user_headers)
    assert pos_ok.status_code != 403

    denied = await ac.get("/api/v1/expenses", headers=user_headers)
    assert denied.status_code == 403


@pytest.mark.asyncio
async def test_cannot_delete_custom_role_in_use(client):
    ac, seed = client
    headers = await _admin_headers(ac, seed)
    await ac.post(
        "/api/v1/roles",
        headers=headers,
        json={
            "slug": "temp_role",
            "label": "Temp Role",
            "base_role": "cashier",
        },
    )
    await ac.post(
        "/api/v1/users",
        headers=headers,
        json={
            "email": "temp@alpha.example.com",
            "full_name": "Temp User",
            "password": "SecurePass123!",
            "role": "temp_role",
        },
    )
    blocked = await ac.delete("/api/v1/roles/temp_role", headers=headers)
    assert blocked.status_code == 409

    # Reassign then delete
    users = await ac.get("/api/v1/users", headers=headers)
    uid = next(u["id"] for u in users.json()["data"] if u["email"] == "temp@alpha.example.com")
    await ac.patch(f"/api/v1/users/{uid}", headers=headers, json={"role": "cashier"})
    deleted = await ac.delete("/api/v1/roles/temp_role", headers=headers)
    assert deleted.status_code == 200, deleted.text


@pytest.mark.asyncio
async def test_patch_role_permissions_updates_assigned_users(client, db_session):
    ac, seed = client
    headers = await _admin_headers(ac, seed)
    await ac.post(
        "/api/v1/roles",
        headers=headers,
        json={
            "slug": "stock_helper",
            "label": "Stock Helper",
            "permissions": {
                "dashboard": ["read"],
                "inventory": ["read"],
                "notifications": ["read"],
                "security": ["read", "write"],
            },
        },
    )
    created = await ac.post(
        "/api/v1/users",
        headers=headers,
        json={
            "email": "stock@alpha.example.com",
            "full_name": "Stock Helper",
            "password": "SecurePass123!",
            "role": "stock_helper",
        },
    )
    user_id = created.json()["data"]["id"]

    await ac.put(
        "/api/v1/roles/stock_helper/permissions",
        headers=headers,
        json={
            "permissions": {
                "dashboard": ["read"],
                "inventory": ["read", "write"],
                "notifications": ["read", "write"],
                "security": ["read", "write"],
            }
        },
    )
    user = await db_session.get(m.User, user_id)
    await db_session.refresh(user)
    assert "write" in (user.permissions or {}).get("inventory", [])


def test_has_permission_uses_overrides_as_authority():
    # Custom restrictive map must not inherit cashier POS write.
    custom = {"dashboard": ["read"], "inventory": ["read"]}
    assert has_permission("pos_only", "pos", "read", overrides=custom) is False
    assert has_permission("pos_only", "inventory", "read", overrides=custom) is True
    assert has_permission("cashier", "pos", "write", overrides=None) is True
