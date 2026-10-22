"""Stale User.permissions snapshots must not strip platform_packages:write."""

from __future__ import annotations

from uuid import uuid4

import pyotp
import pytest

from app import models as m
from app.rbac import permissions_for_role
from tests.conftest import auth_headers


async def _owner(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_stale_permissions_snapshot_still_allows_package_assign(client, db_session):
    """Older DB rows stored platform_packages:read only; catalog now includes write."""
    ac, seed = client
    owner = await _owner(ac, seed)
    suffix = uuid4().hex[:8]
    email = f"stale-pkg-{suffix}@alpha.example.com"

    created = await ac.post(
        "/api/v1/platform/staff",
        headers=owner,
        json={
            "email": email,
            "full_name": f"Stale Perms {suffix}",
            "password": "SecurePass123!",
            "role": "platform_finance",
        },
    )
    assert created.status_code == 200, created.text
    uid = created.json()["data"]["id"]
    verified = await ac.post(f"/api/v1/platform/staff/{uid}/verify-email", headers=owner)
    assert verified.status_code == 200, verified.text

    user = await db_session.get(m.User, uid)
    assert user is not None
    # Simulate a pre-catalog snapshot that only had read (the live 403 root cause).
    user.permissions = {
        "platform": ["read"],
        "platform_tenants": ["read"],
        "platform_packages": ["read"],
        "platform_reports": ["read"],
        "users": ["read"],
        "notifications": ["read"],
        "audit": ["read"],
        "security": ["read", "write"],
    }
    await db_session.commit()

    finance = await auth_headers(ac, email=email, tenant_slug="alpha")
    me = await ac.get("/api/v1/me", headers=finance)
    assert me.status_code == 200, me.text
    assert "write" in (me.json()["data"].get("permissions") or {}).get("platform_packages", [])
    catalog = permissions_for_role("platform_finance")["platform_packages"]
    assert "write" in catalog

    assigned = await ac.post(
        f"/api/v1/tenants/{seed['t1'].slug}/subscription",
        headers=finance,
        json={"package_code": "starter", "term_value": 1, "term_unit": "months"},
    )
    assert assigned.status_code == 200, assigned.text
