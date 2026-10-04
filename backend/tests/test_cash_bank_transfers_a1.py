"""Cash/bank account create + transfers (BR-10.3)."""

from __future__ import annotations

import pyotp
import pytest

from tests.conftest import auth_headers


async def _admin(ac, seed):
    # store_manager has accounting:read but not write — use super for write
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_create_liquid_accounts_and_transfer(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)

    petty = await ac.post(
        "/api/v1/accounting/accounts",
        headers=headers,
        json={"code": "1001", "name": "Petty Cash", "liquid_kind": "cash"},
    )
    assert petty.status_code == 200, petty.text
    assert petty.json()["data"]["is_cash_account"] is True

    bank2 = await ac.post(
        "/api/v1/accounting/accounts",
        headers=headers,
        json={
            "code": "1011",
            "name": "Savings Bank",
            "liquid_kind": "bank",
            "bank_name": "Demo Bank",
            "account_number": "998877",
            "bank_branch": "Main",
        },
    )
    assert bank2.status_code == 200, bank2.text
    assert bank2.json()["data"]["bank_branch"] == "Main"

    # Seed cash via deposit so transfer has funds
    liq = await ac.get("/api/v1/accounting/liquid-accounts", headers=headers)
    by_code = {a["code"]: a for a in liq.json()["data"]}
    cash = by_code["1000"]
    bank = by_code["1010"]

    dep = await ac.post(
        "/api/v1/accounting/transfers",
        headers=headers,
        json={"kind": "deposit", "to_account_id": cash["id"], "amount": 500, "reference": "OPEN"},
    )
    assert dep.status_code == 200, dep.text
    assert dep.json()["data"]["kind"] == "deposit"

    xfer = await ac.post(
        "/api/v1/accounting/transfers",
        headers=headers,
        json={
            "kind": "transfer",
            "from_account_id": cash["id"],
            "to_account_id": bank["id"],
            "amount": 150,
            "reference": "TILL-BANK",
            "notes": "End of day",
        },
    )
    assert xfer.status_code == 200, xfer.text
    body = xfer.json()["data"]
    assert body["amount"] == 150
    assert body["journal_entry_id"]

    liq2 = await ac.get("/api/v1/accounting/liquid-accounts", headers=headers)
    bal = {a["code"]: float(a["balance"]) for a in liq2.json()["data"]}
    assert bal["1000"] == 350.0  # 500 - 150
    assert bal["1010"] == 150.0

    listed = await ac.get("/api/v1/accounting/transfers", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()["data"]) >= 2

    # Same-account rejected
    bad = await ac.post(
        "/api/v1/accounting/transfers",
        headers=headers,
        json={
            "kind": "transfer",
            "from_account_id": cash["id"],
            "to_account_id": cash["id"],
            "amount": 10,
        },
    )
    assert bad.status_code == 400

    # Duplicate code
    dup = await ac.post(
        "/api/v1/accounting/accounts",
        headers=headers,
        json={"code": "1001", "name": "Dup", "liquid_kind": "cash"},
    )
    assert dup.status_code == 409

    # Withdrawal
    wd = await ac.post(
        "/api/v1/accounting/transfers",
        headers=headers,
        json={"kind": "withdrawal", "from_account_id": bank["id"], "amount": 50},
    )
    assert wd.status_code == 200, wd.text
    liq3 = await ac.get("/api/v1/accounting/liquid-accounts", headers=headers)
    bal3 = {a["code"]: float(a["balance"]) for a in liq3.json()["data"]}
    assert bal3["1010"] == 100.0

    tb = await ac.get("/api/v1/accounting/trial-balance", headers=headers)
    assert tb.status_code == 200
    assert tb.json()["data"]["balanced"] is True


@pytest.mark.asyncio
async def test_transfer_tenant_isolation(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    liq = await ac.get("/api/v1/accounting/liquid-accounts", headers=headers)
    cash_id = next(a["id"] for a in liq.json()["data"] if a["code"] == "1000")

    from app import models as m
    from app.rbac import permissions_for_role
    from app.security import hash_password
    from sqlalchemy import select

    beta = (
        await db_session.execute(select(m.Tenant).where(m.Tenant.slug == "beta"))
    ).scalar_one()
    mgr = m.User(
        tenant_id=beta.id,
        email="acct@beta.example.com",
        full_name="Beta Acct",
        password_hash=hash_password("SecurePass123!"),
        role="accountant",
        email_verified=True,
        permissions=permissions_for_role("accountant"),
        totp_enabled=False,
    )
    db_session.add(mgr)
    await db_session.commit()

    beta_h = await auth_headers(ac, email="acct@beta.example.com", tenant_slug="beta")
    # Ensure beta has accounts
    await ac.get("/api/v1/accounting/accounts", headers=beta_h)
    steal = await ac.post(
        "/api/v1/accounting/transfers",
        headers=beta_h,
        json={
            "kind": "deposit",
            "to_account_id": cash_id,  # alpha account
            "amount": 99,
        },
    )
    assert steal.status_code == 404, steal.text
