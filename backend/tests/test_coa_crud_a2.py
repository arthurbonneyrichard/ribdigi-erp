"""Stage 3 A2: COA CRUD, hierarchy, opening balances (BR-10.1)."""

from __future__ import annotations

import pyotp
import pytest
from sqlalchemy import select

from app import accounting as accounting_svc
from app import models as m
from app.rbac import permissions_for_role
from app.security import hash_password
from tests.conftest import auth_headers


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_create_account_with_parent_and_tree(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)
    tenant_id = seed["t1"].id
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)
    await db_session.commit()

    listed = await ac.get("/api/v1/accounting/accounts", headers=headers)
    assert listed.status_code == 200, listed.text
    by_code = {r["code"]: r for r in listed.json()["data"]}
    assert by_code["1000"]["is_system"] is True
    assert "3900" in by_code
    cash_id = by_code["1000"]["id"]

    created = await ac.post(
        "/api/v1/accounting/accounts",
        headers=headers,
        json={
            "code": "1050",
            "name": "Till Cash",
            "account_type": "asset",
            "parent_id": cash_id,
        },
    )
    assert created.status_code == 200, created.text
    child = created.json()["data"]
    assert child["parent_id"] == cash_id
    assert child["is_system"] is False

    tree = await ac.get("/api/v1/accounting/accounts?tree=true", headers=headers)
    assert tree.status_code == 200
    roots = tree.json()["data"]
    cash_node = next(n for n in roots if n["code"] == "1000")
    assert any(c["code"] == "1050" for c in cash_node["children"])

    got = await ac.get(f"/api/v1/accounting/accounts/{child['id']}", headers=headers)
    assert got.status_code == 200
    assert got.json()["data"]["name"] == "Till Cash"


@pytest.mark.asyncio
async def test_system_account_edit_blocked_and_non_system_patch(client):
    ac, seed = client
    headers = await _super(ac, seed)

    listed = await ac.get("/api/v1/accounting/accounts", headers=headers)
    cash = next(r for r in listed.json()["data"] if r["code"] == "1000")

    blocked = await ac.patch(
        f"/api/v1/accounting/accounts/{cash['id']}",
        headers=headers,
        json={"name": "Renamed Cash"},
    )
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["code"] == "SYSTEM_ACCOUNT"

    custom = await ac.post(
        "/api/v1/accounting/accounts",
        headers=headers,
        json={"code": "6100", "name": "Rent", "account_type": "expense"},
    )
    assert custom.status_code == 200, custom.text
    cid = custom.json()["data"]["id"]

    patched = await ac.patch(
        f"/api/v1/accounting/accounts/{cid}",
        headers=headers,
        json={"name": "Office Rent"},
    )
    assert patched.status_code == 200
    assert patched.json()["data"]["name"] == "Office Rent"

    deactivated = await ac.patch(
        f"/api/v1/accounting/accounts/{cid}",
        headers=headers,
        json={"is_active": False},
    )
    assert deactivated.status_code == 200
    assert deactivated.json()["data"]["is_active"] is False

    active = await ac.get("/api/v1/accounting/accounts", headers=headers)
    assert all(r["id"] != cid for r in active.json()["data"])


@pytest.mark.asyncio
async def test_parent_type_mismatch_and_cycle(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)
    tenant_id = seed["t1"].id
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)
    await db_session.commit()

    listed = await ac.get("/api/v1/accounting/accounts", headers=headers)
    by_code = {r["code"]: r for r in listed.json()["data"]}

    bad_type = await ac.post(
        "/api/v1/accounting/accounts",
        headers=headers,
        json={
            "code": "4050",
            "name": "Bad parent type",
            "account_type": "income",
            "parent_id": by_code["1000"]["id"],
        },
    )
    assert bad_type.status_code == 400

    a = await ac.post(
        "/api/v1/accounting/accounts",
        headers=headers,
        json={"code": "1500", "name": "Fixed Assets", "account_type": "asset"},
    )
    b = await ac.post(
        "/api/v1/accounting/accounts",
        headers=headers,
        json={
            "code": "1510",
            "name": "Equipment",
            "account_type": "asset",
            "parent_id": a.json()["data"]["id"],
        },
    )
    assert a.status_code == 200 and b.status_code == 200
    cycle = await ac.patch(
        f"/api/v1/accounting/accounts/{a.json()['data']['id']}",
        headers=headers,
        json={"parent_id": b.json()["data"]["id"]},
    )
    assert cycle.status_code == 400
    assert "cycle" in cycle.json()["detail"].lower()


@pytest.mark.asyncio
async def test_opening_balance_posts_balanced_journal(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)
    tenant_id = seed["t1"].id
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)
    await db_session.commit()

    listed = await ac.get("/api/v1/accounting/accounts", headers=headers)
    by_code = {r["code"]: r for r in listed.json()["data"]}
    cash_id = by_code["1000"]["id"]

    cash = await accounting_svc.get_account_by_code(db_session, tenant_id, "1000")
    equity = await accounting_svc.get_account_by_code(db_session, tenant_id, "3900")
    cash_before = float(cash.balance or 0)
    equity_before = float(equity.balance or 0)

    ob = await ac.post(
        f"/api/v1/accounting/accounts/{cash_id}/opening-balance",
        headers=headers,
        json={"amount": 250, "description": "Go-live cash"},
    )
    assert ob.status_code == 200, ob.text
    entry = ob.json()["data"]
    assert entry["status"] == "posted"
    assert entry["source_type"] == "opening_balance"
    assert abs(float(entry["total_debit"]) - float(entry["total_credit"])) < 0.01

    await db_session.refresh(cash)
    await db_session.refresh(equity)
    assert float(cash.balance or 0) == cash_before + 250
    # Equity increases with credit
    assert float(equity.balance or 0) == equity_before + 250

    dup = await ac.post(
        f"/api/v1/accounting/accounts/{cash_id}/opening-balance",
        headers=headers,
        json={"amount": 10},
    )
    assert dup.status_code == 409
    assert dup.json()["detail"]["code"] == "OPENING_BALANCE_EXISTS"

    # Liability natural credit
    ap_id = by_code["2000"]["id"]
    ap_ob = await ac.post(
        f"/api/v1/accounting/accounts/{ap_id}/opening-balance",
        headers=headers,
        json={"amount": 80},
    )
    assert ap_ob.status_code == 200, ap_ob.text
    ap = await accounting_svc.get_account_by_code(db_session, tenant_id, "2000")
    await db_session.refresh(ap)
    assert float(ap.balance or 0) == 80


@pytest.mark.asyncio
async def test_coa_tenant_isolation(client, db_session):
    ac, seed = client
    tenant_a = seed["t1"].id
    tenant_b = seed["t2"].id
    db_session.add(
        m.User(
            tenant_id=tenant_b,
            email="acct2@beta.example.com",
            full_name="Beta Accountant",
            password_hash=hash_password("SecurePass123!"),
            role="accountant",
            email_verified=True,
            permissions=permissions_for_role("accountant"),
            totp_enabled=False,
        )
    )
    await accounting_svc.ensure_default_accounts(db_session, tenant_a)
    custom = await accounting_svc.create_coa_account(
        db_session,
        tenant_id=tenant_a,
        code="1999",
        name="Alpha Only",
        account_type="asset",
    )
    await db_session.commit()

    headers_b = await auth_headers(ac, email="acct2@beta.example.com", tenant_slug="beta")
    g = await ac.get(f"/api/v1/accounting/accounts/{custom.id}", headers=headers_b)
    assert g.status_code == 404
    p = await ac.patch(
        f"/api/v1/accounting/accounts/{custom.id}",
        headers=headers_b,
        json={"name": "Hijack"},
    )
    assert p.status_code == 404
