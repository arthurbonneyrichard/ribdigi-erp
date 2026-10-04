"""Tenant subscription packages + feature entitlements (software owner)."""

from __future__ import annotations

from datetime import datetime, timedelta

import pyotp
import pytest
from sqlalchemy import select

from app import models as m
from app import packages as packages_svc
from app import tenants as tenants_svc
from tests.conftest import auth_headers


def test_add_months_and_usage_math():
    start = datetime(2026, 1, 31, 12, 0, 0)
    assert packages_svc.add_calendar_months(start, 1).month == 2
    assert packages_svc.term_to_months(2, "years") == 24
    assert packages_svc.months_between(datetime(2026, 1, 15), datetime(2026, 4, 20)) == 3


def test_package_modules_starter_excludes_ai():
    mods = packages_svc.package_modules("starter")
    assert "pos" in mods
    assert "ai" not in mods
    assert "purchasing" not in mods
    assert "ai" in packages_svc.package_modules("professional")


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_assign_subscription_and_usage(client, db_session):
    ac, seed = client
    tid = seed["t1"].id
    tenant = await tenants_svc.get_tenant(db_session, tid)
    await tenants_svc.assign_subscription(
        db_session,
        tenant,
        package_code="starter",
        term_value=1,
        term_unit="years",
        start_at=datetime.utcnow() - timedelta(days=40),
        activate=True,
    )
    await db_session.commit()
    await db_session.refresh(tenant)
    usage = packages_svc.usage_snapshot(tenant)
    assert usage["package_code"] == "starter"
    assert usage["months_assigned"] == 12
    assert usage["years_assigned"] == 1.0
    assert usage["months_used"] >= 1
    assert usage["months_remaining"] is not None
    assert usage["months_remaining"] < 12
    assert "ai" not in usage["enabled_modules"]
    assert "pos" in usage["enabled_modules"]


@pytest.mark.asyncio
async def test_platform_assign_subscription_api(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)

    r = await ac.get("/api/v1/packages", headers=headers)
    assert r.status_code == 200, r.text
    assert any(p["code"] == "professional" for p in r.json()["data"]["packages"])

    r2 = await ac.post(
        f"/api/v1/tenants/{seed['t1'].slug}/subscription",
        headers=headers,
        json={
            "package_code": "starter",
            "term_value": 6,
            "term_unit": "months",
            "activate": True,
        },
    )
    assert r2.status_code == 200, r2.text
    data = r2.json()["data"]
    assert data["package_code"] == "starter"
    assert data["subscription"]["months_assigned"] == 6
    assert data["subscription"]["months_remaining"] is not None
    assert "ai" not in data["enabled_modules"]

    r3 = await ac.patch(
        f"/api/v1/tenants/{seed['t1'].slug}/modules",
        headers=headers,
        json={"enabled_modules": ["dashboard", "inventory", "notifications", "security"]},
    )
    assert r3.status_code == 200, r3.text
    assert "pos" not in r3.json()["data"]["enabled_modules"]

    mgr = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    blocked = await ac.get("/api/v1/pos/sessions", headers=mgr)
    assert blocked.status_code == 403, blocked.text
    detail = blocked.json()["detail"]
    assert isinstance(detail, dict)
    assert detail.get("code") == "PACKAGE_FEATURE_DISABLED"

    ok = await ac.get("/api/v1/products", headers=mgr)
    assert ok.status_code == 200, ok.text

    # Reset restores package modules including pos
    r4 = await ac.patch(
        f"/api/v1/tenants/{seed['t1'].slug}/modules",
        headers=headers,
        json={"reset_to_package": True},
    )
    assert r4.status_code == 200, r4.text
    assert "pos" in r4.json()["data"]["enabled_modules"]
