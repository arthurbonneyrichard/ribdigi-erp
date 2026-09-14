"""ADR-005 Phase E — automated flag-ON membership scope soak (Complete).

Exercises STORE_MEMBERSHIP_SCOPE_ENABLED=true end-to-end without flipping the
production default. ADR-005 Complete = feature complete + this automated soak
(SEC-M2-style). Complete ≠ production default ON.
"""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest
from sqlalchemy import select

from app import dashboard_scope as dashboard_scope_svc
from app import models as m
from app import store_memberships as store_memberships_svc
from app.config import Settings
from app.rbac import permissions_for_role
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _super_headers(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


def _enable_membership_scope(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.config.settings.STORE_MEMBERSHIP_SCOPE_ENABLED", True
    )
    monkeypatch.setattr(
        "app.dashboard_scope.settings.STORE_MEMBERSHIP_SCOPE_ENABLED", True
    )
    monkeypatch.setattr(
        "app.store_memberships.settings.STORE_MEMBERSHIP_SCOPE_ENABLED", True
    )


def _disable_membership_scope(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.config.settings.STORE_MEMBERSHIP_SCOPE_ENABLED", False
    )
    monkeypatch.setattr(
        "app.dashboard_scope.settings.STORE_MEMBERSHIP_SCOPE_ENABLED", False
    )
    monkeypatch.setattr(
        "app.store_memberships.settings.STORE_MEMBERSHIP_SCOPE_ENABLED", False
    )


async def _grant_cashier_stores_read(db_session, cashier, company_id: str) -> None:
    """Workspace overrides user.permissions — grant stores:read on company membership."""
    perms = dict(permissions_for_role("cashier"))
    perms["stores"] = ["read"]
    user_row = await db_session.get(m.User, cashier.id)
    assert user_row is not None
    user_row.permissions = perms
    mem = (
        await db_session.execute(
            select(m.UserCompanyMembership).where(
                m.UserCompanyMembership.user_id == cashier.id,
                m.UserCompanyMembership.company_id == company_id,
            )
        )
    ).scalar_one()
    mem.permissions = perms
    await db_session.commit()


def _assert_complete_honesty(payload: dict, *, flag_on: bool) -> None:
    assert payload["adr005_complete_claimed"] is True
    assert payload["store_scoped_rbac_complete_claimed"] is False
    assert payload["scope_wired_to_membership"] is True
    assert payload["scaffold_status"] == "complete"
    assert payload["store_membership_scope_enabled"] is flag_on
    assert payload["cashier_membership_fail_closed"] is flag_on
    assert "automated_flag_on_soak" in (payload.get("complete_means") or "")


def test_adr005_soak_flag_still_defaults_off_ops_enable():
    """Complete soak does not flip production default — ops enable is cutover."""
    cfg = Settings(APP_ENV="development")
    assert cfg.STORE_MEMBERSHIP_SCOPE_ENABLED is False

    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "STORE_MEMBERSHIP_SCOPE_ENABLED=false" in example

    prod = (ROOT / ".env.production.example").read_text(encoding="utf-8")
    assert "STORE_MEMBERSHIP_SCOPE_ENABLED=false" in prod
    assert "ADR-005" in prod or "membership" in prod.lower()


def test_adr005_soak_honesty_complete_flags():
    honesty = store_memberships_svc.honesty_payload()
    _assert_complete_honesty(honesty, flag_on=False)
    assert store_memberships_svc.ADR005_COMPLETE_CLAIMED is True
    assert store_memberships_svc.SCOPE_WIRED_TO_MEMBERSHIP is True
    assert store_memberships_svc.STORE_SCOPED_RBAC_COMPLETE_CLAIMED is False


def test_adr005_soak_docs_and_checklist_present():
    cutover = (ROOT / "docs/ADR_005_MEMBERSHIP_SCOPE_CUTOVER.md").read_text(
        encoding="utf-8"
    )
    assert "STORE_MEMBERSHIP_SCOPE_ENABLED" in cutover
    assert "Complete" in cutover
    assert "fail-closed" in cutover.lower() or "fail_closed" in cutover.lower()
    assert "production default" in cutover.lower() or "prod default" in cutover.lower()

    checklist = (ROOT / "docs/adr005_staging_soak_checklist.md").read_text(
        encoding="utf-8"
    )
    assert "STORE_MEMBERSHIP_SCOPE_ENABLED" in checklist
    assert "test_adr005_membership_scope_soak.py" in checklist
    assert "Complete" in checklist
    cl = checklist.lower()
    assert "ops" in cl or "staging" in cl
    assert "default" in cl and "false" in cl


@pytest.mark.asyncio
async def test_adr005_soak_flag_off_legacy_manager_and_cashier(
    client, db_session, monkeypatch
):
    """Flag OFF: manager_id-only scope; cashier POS company-wide (legacy)."""
    _disable_membership_scope(monkeypatch)
    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    mgr = seed["mgr1"]
    cashier = seed["u1"]

    managed_store = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Soak Legacy Managed",
        code="SOAK-LEG-MGR",
        manager_id=mgr.id,
        is_active=True,
    )
    membership_only = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Soak Legacy Mem Only",
        code="SOAK-LEG-MEM",
        manager_id=None,
        is_active=True,
    )
    cash_store = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Soak Legacy Cash Store",
        code="SOAK-LEG-CASH",
        manager_id=None,
        is_active=True,
    )
    db_session.add_all([managed_store, membership_only, cash_store])
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

    mgr_claims = {
        "sub": mgr.id,
        "tenant_id": tid,
        "role": "store_manager",
        "company_id": cid,
    }
    managed = await dashboard_scope_svc.managed_store_ids(db_session, mgr_claims)
    assert managed is not None
    assert managed_store.id in managed
    assert membership_only.id not in managed

    cash_claims = {
        "sub": cashier.id,
        "tenant_id": tid,
        "role": "cashier",
        "company_id": cid,
    }
    assert await dashboard_scope_svc.managed_store_ids(db_session, cash_claims) is None
    assert await dashboard_scope_svc.store_visibility_ids(db_session, cash_claims) is None

    cash_headers = await auth_headers(
        ac, email="cashier@alpha.example.com", tenant_slug="alpha"
    )
    open_ok = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=cash_headers,
        json={"store_id": cash_store.id, "opening_cash": 10},
    )
    assert open_ok.status_code == 200, open_ok.text
    await ac.post(
        f"/api/v1/pos/sessions/{open_ok.json()['data']['session_id']}/close",
        headers=cash_headers,
        json={"actual_cash": 10},
    )

    honesty = store_memberships_svc.honesty_payload()
    _assert_complete_honesty(honesty, flag_on=False)
    assert honesty["operational_scope"].startswith("stores.manager_id")


@pytest.mark.asyncio
async def test_adr005_soak_flag_on_store_manager_union_scope(
    client, db_session, monkeypatch
):
    """Flag ON: store_manager sees manager_id ∪ membership stores on GET /stores."""
    _enable_membership_scope(monkeypatch)
    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    mgr = seed["mgr1"]

    managed_store = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Soak Union Managed",
        code="SOAK-UN-MGR",
        manager_id=mgr.id,
        is_active=True,
    )
    membership_only = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Soak Union Mem Only",
        code="SOAK-UN-MEM",
        manager_id=None,
        is_active=True,
    )
    foreign = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Soak Union Foreign",
        code="SOAK-UN-X",
        manager_id=None,
        is_active=True,
    )
    db_session.add_all([managed_store, membership_only, foreign])
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
    assert set(managed) >= {managed_store.id, membership_only.id}
    assert foreign.id not in managed
    visible = await dashboard_scope_svc.store_visibility_ids(db_session, claims)
    assert set(visible or []) == set(managed)

    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    listed = await ac.get("/api/v1/stores", headers=headers)
    assert listed.status_code == 200, listed.text
    ids = {row["id"] for row in listed.json()["data"]}
    assert managed_store.id in ids
    assert membership_only.id in ids
    assert foreign.id not in ids

    honesty = store_memberships_svc.honesty_payload()
    _assert_complete_honesty(honesty, flag_on=True)
    assert "user_store_memberships" in honesty["operational_scope"]


@pytest.mark.asyncio
async def test_adr005_soak_flag_on_cashier_with_membership_only_assigned(
    client, db_session, monkeypatch
):
    """Flag ON: cashier with membership sees only assigned stores; POS OK there."""
    _enable_membership_scope(monkeypatch)
    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    cashier = seed["u1"]

    mine = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Soak Cash Mine",
        code="SOAK-CASH-MINE",
        manager_id=None,
        is_active=True,
    )
    other = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Soak Cash Other",
        code="SOAK-CASH-OTHER",
        manager_id=None,
        is_active=True,
    )
    db_session.add_all([mine, other])
    await db_session.flush()
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
    await _grant_cashier_stores_read(db_session, cashier, cid)

    claims = {
        "sub": cashier.id,
        "tenant_id": tid,
        "role": "cashier",
        "company_id": cid,
    }
    # Continuum path: cashiers stay None on managed_store_ids
    assert await dashboard_scope_svc.managed_store_ids(db_session, claims) is None
    visible = await dashboard_scope_svc.store_visibility_ids(db_session, claims)
    assert set(visible or []) == {mine.id}

    headers = await auth_headers(
        ac, email="cashier@alpha.example.com", tenant_slug="alpha"
    )
    listed = await ac.get("/api/v1/stores", headers=headers)
    assert listed.status_code == 200, listed.text
    assert {row["id"] for row in listed.json()["data"]} == {mine.id}

    ok = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=headers,
        json={"store_id": mine.id, "opening_cash": 15},
    )
    assert ok.status_code == 200, ok.text
    await ac.post(
        f"/api/v1/pos/sessions/{ok.json()['data']['session_id']}/close",
        headers=headers,
        json={"actual_cash": 15},
    )

    denied = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=headers,
        json={"store_id": other.id, "opening_cash": 10},
    )
    assert denied.status_code == 403, denied.text
    detail = denied.json().get("detail") or {}
    if isinstance(detail, dict):
        assert detail.get("code") == "STORE_SCOPE_DENIED"


@pytest.mark.asyncio
async def test_adr005_soak_flag_on_cashier_without_membership_empty_denied(
    client, db_session, monkeypatch
):
    """Flag ON: cashier with no memberships → empty GET /stores + POS denied."""
    _enable_membership_scope(monkeypatch)
    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    cashier = seed["u1"]

    orphan = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Soak Cash Orphan",
        code="SOAK-CASH-ORPH",
        manager_id=None,
        is_active=True,
    )
    db_session.add(orphan)
    await db_session.commit()
    await _grant_cashier_stores_read(db_session, cashier, cid)

    claims = {
        "sub": cashier.id,
        "tenant_id": tid,
        "role": "cashier",
        "company_id": cid,
    }
    assert await dashboard_scope_svc.managed_store_ids(db_session, claims) is None
    assert await dashboard_scope_svc.store_visibility_ids(db_session, claims) == []

    headers = await auth_headers(
        ac, email="cashier@alpha.example.com", tenant_slug="alpha"
    )
    listed = await ac.get("/api/v1/stores", headers=headers)
    assert listed.status_code == 200, listed.text
    assert listed.json()["data"] == []

    denied = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=headers,
        json={"store_id": orphan.id, "opening_cash": 10},
    )
    assert denied.status_code == 403, denied.text
    detail = denied.json().get("detail") or {}
    if isinstance(detail, dict):
        assert detail.get("code") == "STORE_SCOPE_DENIED"

    denied_unset = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=headers,
        json={"opening_cash": 10},
    )
    assert denied_unset.status_code == 403, denied_unset.text


@pytest.mark.asyncio
async def test_adr005_soak_flag_on_admin_unaffected(
    client, db_session, monkeypatch
):
    """Flag ON: admin bypass — managed_store_ids None; sees all company stores."""
    _enable_membership_scope(monkeypatch)
    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id

    s1 = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Soak Admin S1",
        code="SOAK-ADM-1",
        manager_id=None,
        is_active=True,
    )
    s2 = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Soak Admin S2",
        code="SOAK-ADM-2",
        manager_id=None,
        is_active=True,
    )
    db_session.add_all([s1, s2])
    await db_session.commit()

    admin_claims = {
        "sub": seed["admin1"].id,
        "tenant_id": tid,
        "role": "company_admin",
        "company_id": cid,
    }
    super_claims = {
        "sub": seed["super"].id,
        "tenant_id": tid,
        "role": "super_admin",
        "company_id": cid,
    }
    assert await dashboard_scope_svc.managed_store_ids(db_session, admin_claims) is None
    assert await dashboard_scope_svc.store_visibility_ids(db_session, admin_claims) is None
    assert await dashboard_scope_svc.managed_store_ids(db_session, super_claims) is None
    assert await dashboard_scope_svc.store_visibility_ids(db_session, super_claims) is None

    # company_admin may require 2FA enrollment in this env — use enrolled super for HTTP
    headers = await _super_headers(ac, seed)
    listed = await ac.get("/api/v1/stores", headers=headers)
    assert listed.status_code == 200, listed.text
    ids = {row["id"] for row in listed.json()["data"]}
    assert s1.id in ids and s2.id in ids

    # Membership admin APIs remain admin-gated (store_manager still 403)
    mgr_headers = await auth_headers(
        ac, email="mgr@alpha.example.com", tenant_slug="alpha"
    )
    denied = await ac.get(f"/api/v1/stores/{s1.id}/memberships", headers=mgr_headers)
    assert denied.status_code == 403, denied.text

    assigned = await ac.post(
        f"/api/v1/stores/{s1.id}/memberships",
        headers=headers,
        json={"user_id": seed["u1"].id},
    )
    assert assigned.status_code == 200, assigned.text
    body = assigned.json()["data"]
    _assert_complete_honesty(body, flag_on=True)


@pytest.mark.asyncio
async def test_adr005_soak_me_memberships_honesty_and_visibility_flag_on(
    client, db_session, monkeypatch
):
    """Flag ON: /me/store-memberships returns visibility + Complete honesty."""
    _enable_membership_scope(monkeypatch)
    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    cashier = seed["u1"]

    store = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Soak Me Store",
        code="SOAK-ME-1",
        manager_id=None,
        is_active=True,
    )
    db_session.add(store)
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

    headers = await auth_headers(
        ac, email="cashier@alpha.example.com", tenant_slug="alpha"
    )
    mine = await ac.get("/api/v1/me/store-memberships", headers=headers)
    assert mine.status_code == 200, mine.text
    body = mine.json()["data"]
    _assert_complete_honesty(body, flag_on=True)
    assert any(r["store_id"] == store.id for r in body["memberships"])
    assert "user_store_memberships" in body["operational_scope"]
    assert body["pos_store_bind_required"] is True
    assert set(body["store_visibility_ids"] or []) == {store.id}


@pytest.mark.asyncio
async def test_adr005_soak_flag_on_store_manager_membership_only(
    client, db_session, monkeypatch
):
    """Flag ON: store_manager with membership but no manager_id → membership only."""
    _enable_membership_scope(monkeypatch)
    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    mgr = seed["mgr1"]

    mem_store = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Soak Mem Only Mgr",
        code="SOAK-MEMONLY-1",
        manager_id=None,
        is_active=True,
    )
    foreign = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Soak Mem Only Foreign",
        code="SOAK-MEMONLY-X",
        manager_id=None,
        is_active=True,
    )
    db_session.add_all([mem_store, foreign])
    await db_session.flush()
    db_session.add(
        m.UserStoreMembership(
            tenant_id=tid,
            company_id=cid,
            user_id=mgr.id,
            store_id=mem_store.id,
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
    assert mem_store.id in managed
    assert foreign.id not in managed


@pytest.mark.asyncio
async def test_adr005_soak_me_memberships_visibility_flag_off_no_bind(
    client, db_session, monkeypatch
):
    """Flag OFF: /me visibility null → POS bind not required (legacy)."""
    _disable_membership_scope(monkeypatch)
    ac, seed = client
    headers = await auth_headers(
        ac, email="cashier@alpha.example.com", tenant_slug="alpha"
    )
    mine = await ac.get("/api/v1/me/store-memberships", headers=headers)
    assert mine.status_code == 200, mine.text
    body = mine.json()["data"]
    _assert_complete_honesty(body, flag_on=False)
    assert body["store_visibility_ids"] is None
    assert body["pos_store_bind_required"] is False
