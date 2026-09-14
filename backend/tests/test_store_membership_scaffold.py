"""ADR-005 user↔store membership scaffold — Complete still MISSING."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from app import dashboard_scope as dashboard_scope_svc
from app import models as m
from app import store_memberships as store_memberships_svc
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
    assert body["adr005_complete_claimed"] is False
    assert body["scope_wired_to_membership"] is False
    assert body["scaffold_status"] == "partial"

    listed = await ac.get(f"/api/v1/stores/{store.id}/memberships", headers=headers)
    assert listed.status_code == 200, listed.text
    lbody = listed.json()["data"]
    assert lbody["adr005_complete_claimed"] is False
    assert any(r["user_id"] == cashier.id for r in lbody["memberships"])

    cash_headers = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    mine = await ac.get("/api/v1/me/store-memberships", headers=cash_headers)
    assert mine.status_code == 200, mine.text
    mbody = mine.json()["data"]
    assert mbody["adr005_complete_claimed"] is False
    assert mbody["operational_scope"] == "stores.manager_id"
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
    """Scaffold rows must not change store_manager operational scope."""
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


def test_adr005_scaffold_docs_and_honesty_flags():
    adr = (ROOT / "docs/ADR_005_USER_STORE_ASSIGNMENT.md").read_text(encoding="utf-8")
    assert "scaffold" in adr.lower() or "PARTIAL" in adr
    assert "Complete" in adr
    scaffold = (ROOT / "docs/ADR_005_MEMBERSHIP_SCAFFOLD.md").read_text(encoding="utf-8")
    assert "PARTIAL" in scaffold
    assert "adr005_complete_claimed" in scaffold.lower() or "Complete still MISSING" in scaffold
    assert "manager_id" in scaffold
    honesty = store_memberships_svc.honesty_payload()
    assert honesty["adr005_complete_claimed"] is False
    assert honesty["store_scoped_rbac_complete_claimed"] is False
    assert honesty["scope_wired_to_membership"] is False
    assert honesty["scaffold_status"] == "partial"
