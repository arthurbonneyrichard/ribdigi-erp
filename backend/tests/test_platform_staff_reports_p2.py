"""Platform staff roles + cross-tenant platform reports."""

from __future__ import annotations

import pyotp
import pytest

from app.rbac import (
    PLATFORM_ROLES,
    can_assign_platform_role,
    is_platform_role,
    permissions_for_role,
)
from tests.conftest import auth_headers


def test_platform_role_catalog():
    assert is_platform_role("platform_admin")
    assert is_platform_role("super_admin")
    assert not is_platform_role("company_admin")
    assert "platform_reports" in permissions_for_role("platform_finance")
    assert can_assign_platform_role("platform_owner", "platform_support")
    assert not can_assign_platform_role("platform_support", "platform_admin")
    assert can_assign_platform_role("super_admin", "platform_owner")


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_platform_staff_create_and_reports(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)

    roles = await ac.get("/api/v1/platform/roles", headers=headers)
    assert roles.status_code == 200, roles.text
    keys = {r["key"] for r in roles.json()["data"]}
    assert keys == set(PLATFORM_ROLES)

    created = await ac.post(
        "/api/v1/platform/staff",
        headers=headers,
        json={
            "email": "support@alpha.example.com",
            "full_name": "Platform Support",
            "password": "SecurePass123!",
            "role": "platform_support",
        },
    )
    assert created.status_code == 200, created.text
    assert created.json()["data"]["role"] == "platform_support"

    listed = await ac.get("/api/v1/platform/staff", headers=headers)
    assert listed.status_code == 200
    emails = {u["email"] for u in listed.json()["data"]}
    assert "support@alpha.example.com" in emails
    assert "super@alpha.example.com" in emails

    # Tenant /users cannot mint platform roles
    mgr = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    # mgr lacks users:write typically - use admin
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    blocked = await ac.post(
        "/api/v1/users",
        headers=admin,
        json={
            "email": "nope@alpha.example.com",
            "full_name": "Nope",
            "password": "SecurePass123!",
            "role": "platform_finance",
        },
    )
    assert blocked.status_code in {400, 403, 422}, blocked.text

    reports = await ac.get("/api/v1/platform/reports", headers=headers)
    assert reports.status_code == 200, reports.text
    body = reports.json()["data"]
    assert body["summary"]["tenant_count"] >= 2
    assert "packages" in body
    assert "subscriptions" in body
    assert "trials" in body

    # Support staff can read tenants + reports, not create staff
    # Login as new support — may need email_verified already true
    support_headers = await auth_headers(
        ac, email="support@alpha.example.com", tenant_slug="alpha"
    )
    ok_tenants = await ac.get("/api/v1/tenants", headers=support_headers)
    assert ok_tenants.status_code == 200, ok_tenants.text
    ok_reports = await ac.get("/api/v1/platform/reports/summary", headers=support_headers)
    assert ok_reports.status_code == 200, ok_reports.text
    deny_staff = await ac.post(
        "/api/v1/platform/staff",
        headers=support_headers,
        json={
            "email": "x@alpha.example.com",
            "full_name": "X",
            "password": "SecurePass123!",
            "role": "platform_finance",
        },
    )
    assert deny_staff.status_code == 403, deny_staff.text

    deny_assign = await ac.post(
        f"/api/v1/tenants/{seed['t1'].slug}/subscription",
        headers=support_headers,
        json={"package_code": "starter", "term_value": 1, "term_unit": "months"},
    )
    assert deny_assign.status_code == 403, deny_assign.text
