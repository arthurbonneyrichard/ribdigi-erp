"""Temp store membership expires_at (PARTIAL — elevation/break-glass MISSING)."""

from __future__ import annotations

from datetime import datetime, timedelta

import pyotp
import pytest

from app import dashboard_scope as dashboard_scope_svc
from app import models as m
from app import store_memberships as store_memberships_svc
from app.config import settings
from tests.conftest import auth_headers


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_assign_membership_with_expires_at(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)
    tid = seed["t1"].id
    cid = seed["c1"].id
    cashier = seed["u1"]
    store = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Temp Mem Store",
        code="TEMP-MEM-1",
        manager_id=None,
        is_active=True,
    )
    db_session.add(store)
    await db_session.commit()

    future = (datetime.utcnow() + timedelta(hours=2)).isoformat() + "Z"
    assigned = await ac.post(
        f"/api/v1/stores/{store.id}/memberships",
        headers=headers,
        json={"user_id": cashier.id, "expires_at": future},
    )
    assert assigned.status_code == 200, assigned.text
    body = assigned.json()["data"]
    assert body["expires_at"] is not None
    assert body["is_expired"] is False
    assert body["temp_membership_expires_at_claimed"] is True
    assert body["elevation_break_glass_claimed"] is False

    # Clear expiry → permanent
    cleared = await ac.post(
        f"/api/v1/stores/{store.id}/memberships",
        headers=headers,
        json={"user_id": cashier.id, "expires_at": None},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["data"]["expires_at"] is None


@pytest.mark.asyncio
async def test_expired_membership_excluded_from_scope(client, db_session, monkeypatch):
    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    mgr = seed["mgr1"]
    cashier = seed["u1"]

    monkeypatch.setattr(settings, "STORE_MEMBERSHIP_SCOPE_ENABLED", True)
    monkeypatch.setattr(dashboard_scope_svc.settings, "STORE_MEMBERSHIP_SCOPE_ENABLED", True)
    monkeypatch.setattr(store_memberships_svc.settings, "STORE_MEMBERSHIP_SCOPE_ENABLED", True)

    store = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Expired Scope Store",
        code="EXP-SCOPE-1",
        manager_id=None,
        is_active=True,
    )
    db_session.add(store)
    await db_session.flush()

    past = datetime.utcnow() - timedelta(hours=1)
    future = datetime.utcnow() + timedelta(hours=3)
    expired = m.UserStoreMembership(
        tenant_id=tid,
        company_id=cid,
        user_id=mgr.id,
        store_id=store.id,
        is_active=True,
        expires_at=past,
    )
    live_store = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Live Scope Store",
        code="LIVE-SCOPE-1",
        manager_id=None,
        is_active=True,
    )
    db_session.add(live_store)
    await db_session.flush()
    live = m.UserStoreMembership(
        tenant_id=tid,
        company_id=cid,
        user_id=mgr.id,
        store_id=live_store.id,
        is_active=True,
        expires_at=future,
    )
    cash_expired = m.UserStoreMembership(
        tenant_id=tid,
        company_id=cid,
        user_id=cashier.id,
        store_id=store.id,
        is_active=True,
        expires_at=past,
    )
    db_session.add_all([expired, live, cash_expired])
    await db_session.commit()

    mem_ids = await store_memberships_svc.membership_store_ids(
        db_session, tenant_id=tid, user_id=mgr.id
    )
    assert live_store.id in mem_ids
    assert store.id not in mem_ids

    mgr_claims = {"role": "store_manager", "sub": mgr.id, "tenant_id": tid}
    managed = await dashboard_scope_svc.managed_store_ids(db_session, mgr_claims)
    assert managed is not None
    assert live_store.id in managed
    assert store.id not in managed

    cash_claims = {"role": "cashier", "sub": cashier.id, "tenant_id": tid}
    cash_ids = await dashboard_scope_svc.cashier_membership_store_ids(
        db_session, cash_claims
    )
    assert cash_ids == []

    headers = await _super(ac, seed)
    # /me hides expired rows for the cashier
    cash_h = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    mine = await ac.get("/api/v1/me/store-memberships", headers=cash_h)
    assert mine.status_code == 200, mine.text
    assert all(r["store_id"] != store.id for r in mine.json()["data"]["memberships"])

    # Admin list still surfaces expired-but-active for renewal
    listed = await ac.get(
        f"/api/v1/stores/{store.id}/memberships?active_only=true", headers=headers
    )
    assert listed.status_code == 200, listed.text
    rows = listed.json()["data"]["memberships"]
    cash_row = next(r for r in rows if r["user_id"] == cashier.id)
    assert cash_row["is_expired"] is True
    assert cash_row["expires_at"] is not None


def test_honesty_temp_membership_flags():
    payload = store_memberships_svc.honesty_payload()
    assert payload["temp_membership_expires_at_claimed"] is True
    assert payload["elevation_break_glass_claimed"] is False
    assert payload["adr005_complete_claimed"] is True
    assert payload["store_scoped_rbac_complete_claimed"] is False
