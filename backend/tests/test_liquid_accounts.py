"""BR-10.3 cash/bank liquid accounts + deposit/withdrawal/transfer."""

from __future__ import annotations

import pyotp
import pytest
from sqlalchemy import select

from app.accounting import ensure_default_accounts
from app import models as m
from tests.conftest import auth_headers


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_create_petty_cash_and_bank_accounts(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)

    cash = await ac.post(
        "/api/v1/accounting/liquid-accounts",
        headers=headers,
        json={"kind": "cash", "code": "1005", "name": "Petty Cash"},
    )
    assert cash.status_code == 200, cash.text
    assert cash.json()["data"]["is_cash_account"] is True
    assert cash.json()["data"]["is_bank_account"] is False
    assert cash.json()["data"]["balance"] == 0

    bank = await ac.post(
        "/api/v1/accounting/liquid-accounts",
        headers=headers,
        json={
            "kind": "bank",
            "code": "1015",
            "name": "GTB Operating",
            "bank_name": "GTBank",
            "account_number": "0123456789",
            "bank_branch": "Accra Main",
        },
    )
    assert bank.status_code == 200, bank.text
    data = bank.json()["data"]
    assert data["is_bank_account"] is True
    assert data["bank_name"] == "GTBank"
    assert data["account_number"] == "0123456789"
    assert data["bank_branch"] == "Accra Main"

    dup = await ac.post(
        "/api/v1/accounting/liquid-accounts",
        headers=headers,
        json={"kind": "cash", "code": "1005", "name": "Dup"},
    )
    assert dup.status_code == 409

    missing_bank = await ac.post(
        "/api/v1/accounting/liquid-accounts",
        headers=headers,
        json={"kind": "bank", "code": "1016", "name": "No Bank Name"},
    )
    assert missing_bank.status_code == 400

    patched = await ac.patch(
        f"/api/v1/accounting/liquid-accounts/{bank.json()['data']['id']}",
        headers=headers,
        json={"bank_branch": "Tema Branch", "name": "GTB Ops"},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["data"]["bank_branch"] == "Tema Branch"
    assert patched.json()["data"]["name"] == "GTB Ops"

    liq = await ac.get("/api/v1/accounting/liquid-accounts", headers=headers)
    codes = {r["code"] for r in liq.json()["data"]}
    assert "1005" in codes and "1015" in codes


@pytest.mark.asyncio
async def test_deposit_withdrawal_and_transfer_move_balances(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)
    tenant_id = seed["t1"].id

    await ensure_default_accounts(db_session, tenant_id)
    await db_session.commit()

    seed_je = await ac.post(
        "/api/v1/accounting/journal-entries",
        headers=headers,
        json={
            "description": "Seed cash",
            "lines": [
                {"account_code": "1000", "debit": 500, "credit": 0},
                {"account_code": "4000", "debit": 0, "credit": 500},
            ],
        },
    )
    assert seed_je.status_code == 200, seed_je.text

    liq = await ac.get("/api/v1/accounting/liquid-accounts", headers=headers)
    by_code = {r["code"]: r for r in liq.json()["data"]}
    cash_id = by_code["1000"]["id"]
    bank_id = by_code["1010"]["id"]

    other = await ac.post(
        "/api/v1/accounting/liquid-accounts",
        headers=headers,
        json={
            "kind": "bank",
            "code": "1025",
            "name": "Savings",
            "bank_name": "Ecobank",
            "account_number": "99",
            "bank_branch": "Osu",
        },
    )
    assert other.status_code == 200, other.text
    savings_id = other.json()["data"]["id"]

    deposit = await ac.post(
        "/api/v1/accounting/liquid-transfers",
        headers=headers,
        json={
            "from_account_id": cash_id,
            "to_account_id": bank_id,
            "amount": 200,
            "kind": "deposit",
        },
    )
    assert deposit.status_code == 200, deposit.text
    assert deposit.json()["data"]["source_type"] == "liquid_deposit"

    liq2 = await ac.get("/api/v1/accounting/liquid-accounts", headers=headers)
    by_code = {r["code"]: r for r in liq2.json()["data"]}
    assert by_code["1000"]["balance"] == 300
    assert by_code["1010"]["balance"] == 200

    withdraw = await ac.post(
        "/api/v1/accounting/liquid-transfers",
        headers=headers,
        json={
            "from_account_id": bank_id,
            "to_account_id": cash_id,
            "amount": 50,
            "kind": "withdrawal",
        },
    )
    assert withdraw.status_code == 200, withdraw.text
    assert withdraw.json()["data"]["source_type"] == "liquid_withdrawal"

    transfer = await ac.post(
        "/api/v1/accounting/liquid-transfers",
        headers=headers,
        json={
            "from_account_id": bank_id,
            "to_account_id": savings_id,
            "amount": 75,
        },
    )
    assert transfer.status_code == 200, transfer.text
    assert transfer.json()["data"]["source_type"] == "liquid_transfer"

    liq3 = await ac.get("/api/v1/accounting/liquid-accounts", headers=headers)
    by_code = {r["code"]: r for r in liq3.json()["data"]}
    assert by_code["1000"]["balance"] == 350
    assert by_code["1010"]["balance"] == 75
    assert by_code["1025"]["balance"] == 75

    bad = await ac.post(
        "/api/v1/accounting/liquid-transfers",
        headers=headers,
        json={
            "from_account_id": cash_id,
            "to_account_id": bank_id,
            "amount": 10,
            "kind": "withdrawal",
        },
    )
    assert bad.status_code == 400


@pytest.mark.asyncio
async def test_liquid_transfer_rejects_non_liquid(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)
    tenant_id = seed["t1"].id
    await ensure_default_accounts(db_session, tenant_id)
    await db_session.commit()

    expense = (
        await db_session.execute(
            select(m.Account).where(m.Account.tenant_id == tenant_id, m.Account.code == "6000")
        )
    ).scalar_one()
    cash = (
        await db_session.execute(
            select(m.Account).where(m.Account.tenant_id == tenant_id, m.Account.code == "1000")
        )
    ).scalar_one()

    resp = await ac.post(
        "/api/v1/accounting/liquid-transfers",
        headers=headers,
        json={
            "from_account_id": cash.id,
            "to_account_id": expense.id,
            "amount": 10,
        },
    )
    assert resp.status_code == 400
