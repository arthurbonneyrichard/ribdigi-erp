"""`/me` carries the trial / grace state every dashboard greeting shows, like retail's dashboard."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app import tenants as tenants_svc
from tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_me_returns_subscription_status_for_staff(client, seeded, db_session):
    ac, seed = client
    tenant = seed["t1"]
    tenant.status = "trial"
    tenant.trial_ends_at = datetime.utcnow() + timedelta(days=5)
    db_session.add(tenant)
    await db_session.commit()

    h = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    res = await ac.get("/api/v1/me", headers=h)
    assert res.status_code == 200, res.text
    sub = res.json()["data"]["subscription_status"]
    assert sub["status"] == "trial"
    assert sub["days_remaining"] == 5
    assert sub["trial_ends_at"]
    assert sub["read_only"] is False
    assert sub["trial_days"] == tenants_svc.TRIAL_DAYS


def test_subscription_status_matches_tenant_state():
    class T:
        status = "grace"
        trial_ends_at = None
        grace_ends_at = datetime.utcnow() + timedelta(days=2)

    out = tenants_svc.subscription_status(T())
    assert out["status"] == "grace" and out["days_remaining"] == 2 and out["read_only"] is True
    assert tenants_svc.subscription_status(None)["status"] is None
