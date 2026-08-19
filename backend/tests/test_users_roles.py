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

    # Soft-delete only (ADR-003): row remains; no hard delete
    got = await ac.get(f"/api/v1/users/{user_id}", headers=await _admin_headers(ac, seed))
    assert got.status_code == 200, got.text
    assert got.json()["data"]["id"] == user_id
    assert got.json()["data"]["is_active"] is False
    assert got.json()["data"]["email"] == "newhire@alpha.example.com"

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
