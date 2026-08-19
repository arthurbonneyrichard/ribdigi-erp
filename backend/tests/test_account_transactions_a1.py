"""Stage 8 A1: account ledger transactions drill-down."""

from __future__ import annotations

from datetime import datetime, timedelta

import pyotp
import pytest
from sqlalchemy import select

from app import accounting as accounting_svc
from app import models as m
from tests.conftest import auth_headers


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_account_transactions_running_balance(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    tenant_id = seed["t1"].id
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)
    await db_session.commit()

    cash = (
        await db_session.execute(
            select(m.Account).where(m.Account.tenant_id == tenant_id, m.Account.code == "1000")
        )
    ).scalar_one()

    created = await ac.post(
        "/api/v1/accounting/journal-entries",
        headers=headers,
        json={
            "description": "Ledger drill test",
            "lines": [
                {"account_code": "6000", "debit": 40, "credit": 0},
                {"account_code": "1000", "debit": 0, "credit": 40},
            ],
        },
    )
    assert created.status_code == 200, created.text
    entry_number = created.json()["data"]["entry_number"]

    r = await ac.get(
        f"/api/v1/accounting/accounts/{cash.id}/transactions", headers=headers
    )
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert body["account"]["code"] == "1000"
    assert body["transaction_count"] >= 1
    assert body["total_credit"] >= 40
    hit = next(t for t in body["transactions"] if t["entry_number"] == entry_number)
    assert hit["credit"] == 40.0
    assert hit["debit"] == 0.0
    assert "balance" in hit

    future = (datetime.utcnow() + timedelta(days=30)).date().isoformat()
    filtered = await ac.get(
        f"/api/v1/accounting/accounts/{cash.id}/transactions?from_date={future}",
        headers=headers,
    )
    assert filtered.status_code == 200
    assert filtered.json()["data"]["transaction_count"] == 0
    assert filtered.json()["data"]["opening_balance"] == body["closing_balance"]


@pytest.mark.asyncio
async def test_account_transactions_not_found_and_rbac(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    await accounting_svc.ensure_default_accounts(db_session, seed["t1"].id)
    await db_session.commit()
    cash = (
        await db_session.execute(
            select(m.Account).where(
                m.Account.tenant_id == seed["t1"].id, m.Account.code == "1000"
            )
        )
    ).scalar_one()

    missing = await ac.get(
        "/api/v1/accounting/accounts/00000000-0000-0000-0000-000000000099/transactions",
        headers=headers,
    )
    assert missing.status_code == 404

    cashier = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    denied = await ac.get(
        f"/api/v1/accounting/accounts/{cash.id}/transactions", headers=cashier
    )
    assert denied.status_code == 403
