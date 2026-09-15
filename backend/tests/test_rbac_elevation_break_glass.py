"""RBAC elevation / break-glass MVP (time-bounded grant + reason + audit + expiry)."""

from __future__ import annotations

from datetime import datetime, timedelta

import pyotp
import pytest
from sqlalchemy import select

from app import models as m
from app import rbac_elevations as elev_svc
from app import store_memberships as store_memberships_svc
from app.rbac import has_permission
from app.security import resolve_user_permissions
from tests.conftest import auth_headers


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


def test_honesty_elevation_claimed():
    elev = elev_svc.honesty_payload()
    assert elev["elevation_break_glass_claimed"] is True
    assert elev["store_scoped_rbac_complete_claimed"] is False
    mem = store_memberships_svc.honesty_payload()
    assert mem["elevation_break_glass_claimed"] is True
    assert mem["temp_membership_expires_at_claimed"] is True
    assert mem["store_scoped_rbac_complete_claimed"] is False


def test_merge_and_expiry_helpers():
    merged = elev_svc.merge_permission_maps(
        {"inventory": ["read"]},
        {"inventory": ["write"], "reports": ["export"]},
    )
    assert "read" in merged["inventory"] and "write" in merged["inventory"]
    assert "export" in merged["reports"]

    future = datetime.utcnow() + timedelta(hours=1)
    past = datetime.utcnow() - timedelta(minutes=1)
    live = m.RbacElevation(
        tenant_id="t",
        user_id="u",
        permissions={"inventory": ["write"]},
        reason="emergency stock adjust",
        expires_at=future,
        granted_by="g",
    )
    dead = m.RbacElevation(
        tenant_id="t",
        user_id="u",
        permissions={"inventory": ["write"]},
        reason="stale",
        expires_at=past,
        granted_by="g",
    )
    assert elev_svc.is_elevation_effective(live) is True
    assert elev_svc.is_elevation_effective(dead) is False


@pytest.mark.asyncio
async def test_grant_requires_reason_and_expires_at(client):
    ac, seed = client
    headers = await _super(ac, seed)
    cashier = seed["u1"]

    missing_reason = await ac.post(
        f"/api/v1/users/{cashier.id}/elevations",
        headers=headers,
        json={
            "permissions": {"inventory": ["write"]},
            "expires_at": (datetime.utcnow() + timedelta(hours=1)).isoformat() + "Z",
        },
    )
    assert missing_reason.status_code == 400, missing_reason.text

    missing_exp = await ac.post(
        f"/api/v1/users/{cashier.id}/elevations",
        headers=headers,
        json={
            "permissions": {"inventory": ["write"]},
            "reason": "need inventory write for stock fix",
        },
    )
    assert missing_exp.status_code == 400, missing_exp.text

    past = await ac.post(
        f"/api/v1/users/{cashier.id}/elevations",
        headers=headers,
        json={
            "permissions": {"inventory": ["write"]},
            "reason": "need inventory write for stock fix",
            "expires_at": (datetime.utcnow() - timedelta(hours=1)).isoformat() + "Z",
        },
    )
    assert past.status_code == 400, past.text


@pytest.mark.asyncio
async def test_grant_elevates_then_deny_after_expiry(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)
    cashier = seed["u1"]

    # Cashier baseline lacks inventory:write
    assert not has_permission(
        cashier.role, "inventory", "write", overrides=cashier.permissions or {}
    )

    future = (datetime.utcnow() + timedelta(hours=2)).isoformat() + "Z"
    granted = await ac.post(
        f"/api/v1/users/{cashier.id}/elevations",
        headers=headers,
        json={
            "permissions": {"inventory": ["write"]},
            "reason": "break-glass stock correction after POS outage",
            "expires_at": future,
        },
    )
    assert granted.status_code == 200, granted.text
    body = granted.json()["data"]
    assert body["is_effective"] is True
    assert body["elevation_break_glass_claimed"] is True
    elev_id = body["id"]

    # Effective permissions include elevation
    await db_session.refresh(cashier)
    perms = await resolve_user_permissions(db_session, cashier)
    assert has_permission(cashier.role, "inventory", "write", overrides=perms)

    # Audit trail
    audit_rows = (
        await db_session.execute(
            select(m.AuditLog).where(
                m.AuditLog.tenant_id == seed["t1"].id,
                m.AuditLog.action == "rbac_elevation_grant",
                m.AuditLog.entity_id == elev_id,
            )
        )
    ).scalars().all()
    assert len(audit_rows) >= 1
    assert "break-glass" in (audit_rows[0].details or {}).get("reason", "")

    # Expire → deny
    row = await db_session.get(m.RbacElevation, elev_id)
    row.expires_at = datetime.utcnow() - timedelta(seconds=5)
    await db_session.commit()

    perms_after = await resolve_user_permissions(db_session, cashier)
    assert not has_permission(cashier.role, "inventory", "write", overrides=perms_after)

    mine = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    listed = await ac.get("/api/v1/me/elevations", headers=mine)
    assert listed.status_code == 200, listed.text
    assert listed.json()["data"]["elevations"] == []
    assert listed.json()["data"]["elevation_break_glass_claimed"] is True


@pytest.mark.asyncio
async def test_revoke_denies_immediately(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)
    cashier = seed["u1"]
    future = (datetime.utcnow() + timedelta(hours=1)).isoformat() + "Z"
    granted = await ac.post(
        f"/api/v1/users/{cashier.id}/elevations",
        headers=headers,
        json={
            "permissions": {"reports": ["export"]},
            "reason": "temp export for month-end audit pack",
            "expires_at": future,
        },
    )
    assert granted.status_code == 200, granted.text
    elev_id = granted.json()["data"]["id"]

    revoked = await ac.post(
        f"/api/v1/users/{cashier.id}/elevations/{elev_id}/revoke",
        headers=headers,
    )
    assert revoked.status_code == 200, revoked.text
    assert revoked.json()["data"]["revoked_at"] is not None
    assert revoked.json()["data"]["is_effective"] is False

    await db_session.refresh(cashier)
    perms = await resolve_user_permissions(db_session, cashier)
    assert not has_permission(cashier.role, "reports", "export", overrides=perms)

    audits = (
        await db_session.execute(
            select(m.AuditLog).where(
                m.AuditLog.action == "rbac_elevation_revoke",
                m.AuditLog.entity_id == elev_id,
            )
        )
    ).scalars().all()
    assert len(audits) >= 1


@pytest.mark.asyncio
async def test_cannot_self_elevate(client):
    ac, seed = client
    headers = await _super(ac, seed)
    super_user = seed["super1"] if "super1" in seed else None
    # Resolve super user id from claims via /me
    me = await ac.get("/api/v1/me", headers=headers)
    assert me.status_code == 200, me.text
    my_id = me.json()["data"]["id"]
    resp = await ac.post(
        f"/api/v1/users/{my_id}/elevations",
        headers=headers,
        json={
            "permissions": {"backup": ["read"]},
            "reason": "trying to elevate myself which must fail",
            "expires_at": (datetime.utcnow() + timedelta(hours=1)).isoformat() + "Z",
        },
    )
    assert resp.status_code == 400, resp.text
    _ = super_user


@pytest.mark.asyncio
async def test_store_manager_denied_elevation_admin(client, db_session):
    ac, seed = client
    mgr = seed["mgr1"]
    mgr_h = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    cashier = seed["u1"]
    resp = await ac.post(
        f"/api/v1/users/{cashier.id}/elevations",
        headers=mgr_h,
        json={
            "permissions": {"inventory": ["write"]},
            "reason": "manager should not grant company elevation",
            "expires_at": (datetime.utcnow() + timedelta(hours=1)).isoformat() + "Z",
        },
    )
    assert resp.status_code in (403, 401), resp.text
    _ = mgr
