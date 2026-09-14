"""RBAC hardening slice: owner lockout, grantor subset, permission deps, warnings."""

from __future__ import annotations

import pyotp
import pytest
from fastapi import HTTPException

from app import models as m
from app import roles as roles_svc
from app.rbac import (
    assert_permissions_within_grantor,
    dangerous_permission_warnings,
    ensure_permission_dependencies,
    permissions_within_grantor,
)
from tests.conftest import auth_headers


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


def test_permission_dependencies_auto_add_read():
    out = ensure_permission_dependencies({"inventory": ["write"], "expenses": ["approve"]})
    assert "read" in out["inventory"]
    assert "write" in out["inventory"]
    assert "read" in out["expenses"]
    assert "approve" in out["expenses"]


def test_grantor_subset_blocks_escalation():
    grantor = {"users": ["read", "write"], "inventory": ["read"]}
    missing = permissions_within_grantor({"accounting": ["write"], "inventory": ["read"]}, grantor)
    assert "accounting:write" in missing
    with pytest.raises(ValueError, match="beyond your authority"):
        assert_permissions_within_grantor({"backup": ["read"]}, grantor)


def test_wildcard_grantor_allowed():
    assert permissions_within_grantor({"backup": ["read"], "users": ["write"]}, {"*": ["*"]}) == []


def test_dangerous_permission_warnings():
    warns = dangerous_permission_warnings(
        {"users": ["write"], "pos": ["read"], "credit": ["approve"]}
    )
    mods = {w["module"] for w in warns}
    assert "users" in mods
    assert "credit" in mods
    assert "pos" not in mods


@pytest.mark.asyncio
async def test_custom_role_write_implies_read_and_warnings(client):
    ac, seed = client
    headers = await _super(ac, seed)
    slug = "harden_ops_role"
    created = await ac.post(
        "/api/v1/roles",
        headers=headers,
        json={
            "slug": slug,
            "label": "Harden Ops",
            "permissions": {"inventory": ["write"], "users": ["read"]},
            "record_scope": "own",
        },
    )
    assert created.status_code == 200, created.text
    body = created.json()["data"]
    assert "read" in body["permissions"]["inventory"]
    assert "write" in body["permissions"]["inventory"]
    assert any(w["module"] == "users" for w in body.get("dangerous_permission_warnings") or [])

    put = await ac.put(
        f"/api/v1/roles/{slug}/permissions",
        headers=headers,
        json={"permissions": {"sales": ["approve"], "pos": ["write"]}, "record_scope": "own"},
    )
    assert put.status_code == 200, put.text
    perms = put.json()["data"]["permissions"]
    assert "read" in perms["sales"] and "approve" in perms["sales"]
    assert "read" in perms["pos"] and "write" in perms["pos"]


@pytest.mark.asyncio
async def test_grantor_cannot_escalate_via_custom_role(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)

    limited_slug = "limited_user_admin"
    cr = await ac.post(
        "/api/v1/roles",
        headers=headers,
        json={
            "slug": limited_slug,
            "label": "Limited User Admin",
            "permissions": {
                "users": ["read", "write"],
                "inventory": ["read"],
                "dashboard": ["read"],
                "security": ["read", "write"],
                "notifications": ["read", "write"],
            },
            "record_scope": "all",
        },
    )
    assert cr.status_code == 200, cr.text

    user = await ac.post(
        "/api/v1/users",
        headers=headers,
        json={
            "email": "limited.admin@alpha.example.com",
            "full_name": "Limited Admin",
            "password": "SecurePass123!",
            "role": limited_slug,
        },
    )
    assert user.status_code == 200, user.text
    uid = user.json()["data"]["id"]
    row = await db_session.get(m.User, uid)
    assert row is not None
    row.email_verified = True
    await db_session.commit()

    lim_headers = await auth_headers(
        ac, email="limited.admin@alpha.example.com", tenant_slug="alpha"
    )
    escalate = await ac.post(
        "/api/v1/roles",
        headers=lim_headers,
        json={
            "slug": "should_fail_escalation",
            "label": "Escalation Attempt",
            "permissions": {"accounting": ["read", "write"], "users": ["read"]},
            "record_scope": "own",
        },
    )
    assert escalate.status_code == 403, escalate.text
    assert "authority" in escalate.text.lower()


@pytest.mark.asyncio
async def test_last_super_admin_owner_lockout(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)
    tenant_id = seed["super"].tenant_id

    # Service-level: sole active super_admin cannot be deactivated/demoted.
    with pytest.raises(HTTPException) as blocked:
        await roles_svc.assert_owner_lockout_safe(
            db_session,
            tenant_id=tenant_id,
            target=seed["super"],
            deactivating=True,
        )
    assert blocked.value.status_code == 400
    assert "owner lockout" in str(blocked.value.detail).lower()

    with pytest.raises(HTTPException) as demote:
        await roles_svc.assert_owner_lockout_safe(
            db_session,
            tenant_id=tenant_id,
            target=seed["super"],
            new_role="cashier",
        )
    assert demote.value.status_code == 400
    assert "owner lockout" in str(demote.value.detail).lower()

    # HTTP: adding a second super then removing them leaves lockout intact;
    # non-last deactivate succeeds.
    second = await ac.post(
        "/api/v1/users",
        headers=headers,
        json={
            "email": "super2@alpha.example.com",
            "full_name": "Second Super",
            "password": "SecurePass123!",
            "role": "super_admin",
        },
    )
    assert second.status_code == 200, second.text
    second_id = second.json()["data"]["id"]
    gone = await ac.delete(f"/api/v1/users/{second_id}", headers=headers)
    assert gone.status_code == 200, gone.text

    # After second is gone, HTTP deactivate of last super (self) still blocked as self;
    # peer company_admin path is covered by service assert above (2FA enrollment on CA).
    self_block = await ac.delete(f"/api/v1/users/{seed['super'].id}", headers=headers)
    assert self_block.status_code == 400
    assert "own account" in self_block.text.lower() or "owner lockout" in self_block.text.lower()
