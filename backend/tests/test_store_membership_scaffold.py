"""ADR-005 user↔store membership — Complete via automated soak; flag default OFF."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from app import dashboard_scope as dashboard_scope_svc
from app import models as m
from app import store_memberships as store_memberships_svc
from sqlalchemy import select
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_store_membership_assign_list_revoke_and_me(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)
    tid = seed["t1"].id
    cid = seed["c1"].id
    cashier = seed["u1"]

    store = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Membership Scaffold Store",
        code="MEM-SCAF-1",
        manager_id=None,
        is_active=True,
    )
    db_session.add(store)
    await db_session.commit()

    assigned = await ac.post(
        f"/api/v1/stores/{store.id}/memberships",
        headers=headers,
        json={"user_id": cashier.id},
    )
    assert assigned.status_code == 200, assigned.text
    body = assigned.json()["data"]
    assert body["user_id"] == cashier.id
    assert body["store_id"] == store.id
    assert body["is_active"] is True
    assert body["adr005_complete_claimed"] is True
    assert body["scope_wired_to_membership"] is True
    assert body["scaffold_status"] == "complete"

    listed = await ac.get(f"/api/v1/stores/{store.id}/memberships", headers=headers)
    assert listed.status_code == 200, listed.text
    lbody = listed.json()["data"]
    assert lbody["adr005_complete_claimed"] is True
    assert any(r["user_id"] == cashier.id for r in lbody["memberships"])

    cash_headers = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    mine = await ac.get("/api/v1/me/store-memberships", headers=cash_headers)
    assert mine.status_code == 200, mine.text
    mbody = mine.json()["data"]
    assert mbody["adr005_complete_claimed"] is True
    assert mbody["operational_scope"].startswith("stores.manager_id")
    assert mbody["scope_wired_to_membership"] is True
    assert mbody["scaffold_status"] == "complete"
    assert mbody["store_visibility_ids"] is None
    assert mbody["pos_store_bind_required"] is False
    assert any(r["store_id"] == store.id for r in mbody["memberships"])

    revoked = await ac.delete(
        f"/api/v1/stores/{store.id}/memberships/{cashier.id}",
        headers=headers,
    )
    assert revoked.status_code == 200, revoked.text
    assert revoked.json()["data"]["is_active"] is False

    mine2 = await ac.get("/api/v1/me/store-memberships", headers=cash_headers)
    assert mine2.status_code == 200, mine2.text
    assert all(r["store_id"] != store.id for r in mine2.json()["data"]["memberships"])


@pytest.mark.asyncio
async def test_store_manager_denied_membership_admin_apis(client, db_session):
    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    mgr = seed["mgr1"]
    store = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Mgr Deny Membership",
        code="MEM-DENY-1",
        manager_id=mgr.id,
        is_active=True,
    )
    db_session.add(store)
    await db_session.commit()

    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    denied_list = await ac.get(f"/api/v1/stores/{store.id}/memberships", headers=headers)
    assert denied_list.status_code == 403, denied_list.text

    denied_assign = await ac.post(
        f"/api/v1/stores/{store.id}/memberships",
        headers=headers,
        json={"user_id": seed["u1"].id},
    )
    assert denied_assign.status_code == 403, denied_assign.text


@pytest.mark.asyncio
async def test_membership_does_not_expand_managed_store_ids(client, db_session):
    """Flag OFF (default): scaffold rows must not change store_manager operational scope."""
    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    mgr = seed["mgr1"]

    managed_store = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Managed Via Manager Id",
        code="MEM-MGR-1",
        manager_id=mgr.id,
        is_active=True,
    )
    membership_only = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Membership Only Store",
        code="MEM-ONLY-1",
        manager_id=None,
        is_active=True,
    )
    db_session.add_all([managed_store, membership_only])
    await db_session.flush()
    db_session.add(
        m.UserStoreMembership(
            tenant_id=tid,
            company_id=cid,
            user_id=mgr.id,
            store_id=membership_only.id,
            is_active=True,
        )
    )
    await db_session.commit()

    claims = {
        "sub": mgr.id,
        "tenant_id": tid,
        "role": "store_manager",
        "company_id": cid,
    }
    managed = await dashboard_scope_svc.managed_store_ids(db_session, claims)
    assert managed is not None
    assert managed_store.id in managed
    assert membership_only.id not in managed

    mem_ids = await store_memberships_svc.membership_store_ids(
        db_session, tenant_id=tid, user_id=mgr.id, company_id=cid
    )
    assert membership_only.id in mem_ids
    assert store_memberships_svc.ADR005_COMPLETE_CLAIMED is False
    assert store_memberships_svc.SCOPE_WIRED_TO_MEMBERSHIP is False
    honesty = store_memberships_svc.honesty_payload()
    assert honesty["store_membership_scope_enabled"] is False
    assert honesty["operational_scope"].startswith("stores.manager_id")
    assert honesty["adr005_complete_claimed"] is True
    assert honesty["scope_wired_to_membership"] is True


@pytest.mark.asyncio
async def test_membership_expands_managed_store_ids_when_flag_on(
    client, db_session, monkeypatch
):
    """Flag ON: store_manager scope = manager_id ∪ active memberships."""
    from app.config import settings

    monkeypatch.setattr(settings, "STORE_MEMBERSHIP_SCOPE_ENABLED", True)
    monkeypatch.setattr(dashboard_scope_svc.settings, "STORE_MEMBERSHIP_SCOPE_ENABLED", True)

    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    mgr = seed["mgr1"]

    managed_store = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Managed Via Manager Id Flag On",
        code="MEM-MGR-ON-1",
        manager_id=mgr.id,
        is_active=True,
    )
    membership_only = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Membership Only Flag On",
        code="MEM-ONLY-ON-1",
        manager_id=None,
        is_active=True,
    )
    inactive_mem_store = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Inactive Membership Store",
        code="MEM-INACT-1",
        manager_id=None,
        is_active=True,
    )
    inactive_store = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Inactive Store With Membership",
        code="MEM-ST-OFF-1",
        manager_id=None,
        is_active=False,
    )
    db_session.add_all(
        [managed_store, membership_only, inactive_mem_store, inactive_store]
    )
    await db_session.flush()
    db_session.add_all(
        [
            m.UserStoreMembership(
                tenant_id=tid,
                company_id=cid,
                user_id=mgr.id,
                store_id=membership_only.id,
                is_active=True,
            ),
            m.UserStoreMembership(
                tenant_id=tid,
                company_id=cid,
                user_id=mgr.id,
                store_id=inactive_mem_store.id,
                is_active=False,
            ),
            m.UserStoreMembership(
                tenant_id=tid,
                company_id=cid,
                user_id=mgr.id,
                store_id=inactive_store.id,
                is_active=True,
            ),
        ]
    )
    await db_session.commit()

    claims = {
        "sub": mgr.id,
        "tenant_id": tid,
        "role": "store_manager",
        "company_id": cid,
    }
    managed = await dashboard_scope_svc.managed_store_ids(db_session, claims)
    assert managed is not None
    assert managed_store.id in managed
    assert membership_only.id in managed
    assert inactive_mem_store.id not in managed
    assert inactive_store.id not in managed

    honesty = store_memberships_svc.honesty_payload()
    assert honesty["store_membership_scope_enabled"] is True
    assert "user_store_memberships" in honesty["operational_scope"]
    assert honesty["cashier_membership_fail_closed"] is True
    assert honesty["adr005_complete_claimed"] is True
    assert honesty["scope_wired_to_membership"] is True
    assert honesty["store_scoped_rbac_complete_claimed"] is False


@pytest.mark.asyncio
async def test_flag_on_admin_bypass_cashier_managed_none_visibility_failclosed(
    client, db_session, monkeypatch
):
    """Flag ON: admin bypass; cashier managed_store_ids stays None; visibility fail-closed."""
    from app.config import settings

    monkeypatch.setattr(settings, "STORE_MEMBERSHIP_SCOPE_ENABLED", True)
    monkeypatch.setattr(dashboard_scope_svc.settings, "STORE_MEMBERSHIP_SCOPE_ENABLED", True)

    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    cashier = seed["u1"]

    store = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Cashier Membership Store",
        code="MEM-CASH-1",
        manager_id=None,
        is_active=True,
    )
    foreign = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Cashier Foreign Store",
        code="MEM-CASH-X",
        manager_id=None,
        is_active=True,
    )
    db_session.add_all([store, foreign])
    await db_session.flush()
    db_session.add(
        m.UserStoreMembership(
            tenant_id=tid,
            company_id=cid,
            user_id=cashier.id,
            store_id=store.id,
            is_active=True,
        )
    )
    await db_session.commit()

    admin_claims = {
        "sub": seed["super"].id,
        "tenant_id": tid,
        "role": "company_admin",
        "company_id": cid,
    }
    assert await dashboard_scope_svc.managed_store_ids(db_session, admin_claims) is None
    assert await dashboard_scope_svc.store_visibility_ids(db_session, admin_claims) is None

    cash_claims = {
        "sub": cashier.id,
        "tenant_id": tid,
        "role": "cashier",
        "company_id": cid,
    }
    # Continuum path unchanged — cashiers must not inherit managed_ids is not None denies.
    assert await dashboard_scope_svc.managed_store_ids(db_session, cash_claims) is None
    visible = await dashboard_scope_svc.store_visibility_ids(db_session, cash_claims)
    assert visible is not None
    assert set(visible) == {store.id}
    assert foreign.id not in visible


@pytest.mark.asyncio
async def test_cashier_membership_failclosed_flag_on_off(client, db_session, monkeypatch):
    """Cashier POS open + store list: flag OFF legacy; flag ON membership fail-closed."""
    from app.config import settings
    from app.rbac import permissions_for_role

    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    cashier = seed["u1"]

    mine = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Cashier Mine",
        code="CASH-FC-MINE",
        manager_id=None,
        is_active=True,
    )
    other = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Cashier Other",
        code="CASH-FC-OTHER",
        manager_id=None,
        is_active=True,
    )
    db_session.add_all([mine, other])
    await db_session.commit()

    cash_headers = await auth_headers(
        ac, email="cashier@alpha.example.com", tenant_slug="alpha"
    )
    cash_claims = {
        "sub": cashier.id,
        "tenant_id": tid,
        "role": "cashier",
        "company_id": cid,
    }

    # --- Flag OFF: legacy (no membership filter) ---
    monkeypatch.setattr(settings, "STORE_MEMBERSHIP_SCOPE_ENABLED", False)
    monkeypatch.setattr(dashboard_scope_svc.settings, "STORE_MEMBERSHIP_SCOPE_ENABLED", False)
    assert await dashboard_scope_svc.cashier_membership_store_ids(db_session, cash_claims) is None
    assert await dashboard_scope_svc.store_visibility_ids(db_session, cash_claims) is None

    open_off = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=cash_headers,
        json={"store_id": other.id, "opening_cash": 10},
    )
    assert open_off.status_code == 200, open_off.text
    sess_off_id = open_off.json()["data"]["session_id"]
    closed = await ac.post(
        f"/api/v1/pos/sessions/{sess_off_id}/close",
        headers=cash_headers,
        json={"actual_cash": 10},
    )
    assert closed.status_code == 200, closed.text

    # Grant stores:read on user + company membership (workspace overrides user.permissions).
    perms = dict(permissions_for_role("cashier"))
    perms["stores"] = ["read"]
    user_row = await db_session.get(m.User, cashier.id)
    assert user_row is not None
    user_row.permissions = perms
    mem = (
        await db_session.execute(
            select(m.UserCompanyMembership).where(
                m.UserCompanyMembership.user_id == cashier.id,
                m.UserCompanyMembership.company_id == cid,
            )
        )
    ).scalar_one()
    mem.permissions = perms
    await db_session.commit()
    cash_headers = await auth_headers(
        ac, email="cashier@alpha.example.com", tenant_slug="alpha"
    )

    listed_off = await ac.get("/api/v1/stores", headers=cash_headers)
    assert listed_off.status_code == 200, listed_off.text
    off_ids = {row["id"] for row in listed_off.json()["data"]}
    assert mine.id in off_ids and other.id in off_ids

    # --- Flag ON, no membership: empty visibility + POS denied ---
    monkeypatch.setattr(settings, "STORE_MEMBERSHIP_SCOPE_ENABLED", True)
    monkeypatch.setattr(dashboard_scope_svc.settings, "STORE_MEMBERSHIP_SCOPE_ENABLED", True)
    assert await dashboard_scope_svc.managed_store_ids(db_session, cash_claims) is None
    assert await dashboard_scope_svc.store_visibility_ids(db_session, cash_claims) == []

    listed_empty = await ac.get("/api/v1/stores", headers=cash_headers)
    assert listed_empty.status_code == 200
    assert listed_empty.json()["data"] == []

    denied = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=cash_headers,
        json={"store_id": other.id, "opening_cash": 10},
    )
    assert denied.status_code == 403, denied.text
    detail = denied.json().get("detail") or {}
    if isinstance(detail, dict):
        assert detail.get("code") == "STORE_SCOPE_DENIED"

    # --- Flag ON + membership: only assigned store ---
    db_session.add(
        m.UserStoreMembership(
            tenant_id=tid,
            company_id=cid,
            user_id=cashier.id,
            store_id=mine.id,
            is_active=True,
        )
    )
    await db_session.commit()

    visible = await dashboard_scope_svc.store_visibility_ids(db_session, cash_claims)
    assert set(visible or []) == {mine.id}

    listed_on = await ac.get("/api/v1/stores", headers=cash_headers)
    assert listed_on.status_code == 200
    on_ids = {row["id"] for row in listed_on.json()["data"]}
    assert on_ids == {mine.id}

    ok = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=cash_headers,
        json={"store_id": mine.id, "opening_cash": 25},
    )
    assert ok.status_code == 200, ok.text
    # Close before foreign attempt so 403 is STORE_SCOPE_DENIED (not 409 open shift).
    await ac.post(
        f"/api/v1/pos/sessions/{ok.json()['data']['session_id']}/close",
        headers=cash_headers,
        json={"actual_cash": 25},
    )

    foreign = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=cash_headers,
        json={"store_id": other.id, "opening_cash": 10},
    )
    assert foreign.status_code == 403, foreign.text

    honesty = store_memberships_svc.honesty_payload()
    assert honesty["cashier_membership_fail_closed"] is True
    assert honesty["adr005_complete_claimed"] is True
    assert honesty["scope_wired_to_membership"] is True


def test_adr005_scaffold_docs_and_honesty_flags():
    adr = (ROOT / "docs/ADR_005_USER_STORE_ASSIGNMENT.md").read_text(encoding="utf-8")
    assert "Complete" in adr
    assert "STORE_MEMBERSHIP_SCOPE_ENABLED" in adr
    scaffold = (ROOT / "docs/ADR_005_MEMBERSHIP_SCAFFOLD.md").read_text(encoding="utf-8")
    assert "Complete" in scaffold
    assert "adr005_complete_claimed" in scaffold.lower()
    assert "manager_id" in scaffold
    cutover = (ROOT / "docs/ADR_005_MEMBERSHIP_SCOPE_CUTOVER.md").read_text(encoding="utf-8")
    assert "STORE_MEMBERSHIP_SCOPE_ENABLED" in cutover
    assert "union" in cutover.lower()
    assert "Complete" in cutover
    assert "cashier" in cutover.lower()
    assert "fail-closed" in cutover.lower() or "fail_closed" in cutover.lower()
    assert "production default" in cutover.lower() or "prod default" in cutover.lower()
    honesty = store_memberships_svc.honesty_payload()
    assert honesty["adr005_complete_claimed"] is True
    assert honesty["store_scoped_rbac_complete_claimed"] is False
    assert honesty["scope_wired_to_membership"] is True
    assert honesty["scaffold_status"] == "complete"
    assert "cashier_membership_fail_closed" in honesty
