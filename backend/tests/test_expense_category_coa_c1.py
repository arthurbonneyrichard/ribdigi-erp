"""Expense category GL account for auto-posting (BR-9.2)."""

from __future__ import annotations

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
async def test_category_account_posts_to_linked_gl(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    tenant_id = seed["t1"].id
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)
    await db_session.commit()

    # Create a dedicated expense GL under 6100
    gl = await ac.post(
        "/api/v1/accounting/accounts",
        headers=headers,
        json={
            "code": "6100",
            "name": "Marketing Expense",
            "account_type": "expense",
        },
    )
    assert gl.status_code == 200, gl.text
    account_id = gl.json()["data"]["id"]

    # Cash account cannot be linked
    cash = await accounting_svc.get_account_by_code(db_session, tenant_id, "1000")
    bad = await ac.post(
        "/api/v1/expenses/categories",
        headers=headers,
        json={
            "code": "BADGL",
            "name": "Bad GL",
            "account_id": cash.id,
        },
    )
    assert bad.status_code == 400

    cat = await ac.post(
        "/api/v1/expenses/categories",
        headers=headers,
        json={
            "code": "MKTGL",
            "name": "Marketing GL",
            "budget_amount": 100,
            "account_id": account_id,
        },
    )
    assert cat.status_code == 200, cat.text
    cdata = cat.json()["data"]
    assert cdata["account_id"] == account_id
    assert cdata["account_code"] == "6100"
    cat_id = cdata["id"]

    # Keep expense pending→auto-approve under threshold so journal posts
    seed["t1"].expense_approval_threshold = 1000
    seed["t1"].expense_approval_matrix = None
    await db_session.commit()

    created = await ac.post(
        "/api/v1/expenses",
        headers=headers,
        json={
            "category_id": cat_id,
            "amount": 42,
            "description": "Campaign ads",
            "payment_method": "cash",
        },
    )
    assert created.status_code == 200, created.text
    assert created.json()["data"]["status"] == "approved"
    expense_id = created.json()["data"]["id"]

    entry = (
        await db_session.execute(
            select(m.JournalEntry).where(
                m.JournalEntry.tenant_id == tenant_id,
                m.JournalEntry.source_type == "expense",
                m.JournalEntry.source_id == expense_id,
            )
        )
    ).scalar_one()
    lines = (
        await db_session.execute(
            select(m.JournalEntryLine).where(m.JournalEntryLine.journal_entry_id == entry.id)
        )
    ).scalars().all()
    assert any(ln.account_id == account_id and float(ln.debit) == 42 for ln in lines)

    cleared = await ac.patch(
        f"/api/v1/expenses/categories/{cat_id}",
        headers=headers,
        json={"clear_account": True},
    )
    assert cleared.status_code == 200
    assert cleared.json()["data"]["account_id"] is None
