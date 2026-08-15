"""Balance sheet + trial balance store/branch filters (BR-14.5)."""

from __future__ import annotations

import pyotp
import pytest

from app import accounting as accounting_svc
from app import models as m
from tests.conftest import auth_headers


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_bs_tb_store_filter_scopes_attributable_journals(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    tenant_id = seed["t1"].id

    # Ensure CoA exists
    assert (await ac.get("/api/v1/accounting/accounts", headers=headers)).status_code == 200

    store = await ac.post(
        "/api/v1/stores",
        headers=headers,
        json={"code": "BS-S1", "name": "BS Filter Store"},
    )
    assert store.status_code == 200, store.text
    store_id = store.json()["data"]["id"]

    other = await ac.post(
        "/api/v1/stores",
        headers=headers,
        json={"code": "BS-S2", "name": "Other Store"},
    )
    assert other.status_code == 200, other.text
    other_id = other.json()["data"]["id"]

    # Expense attributable to store_id
    exp = m.Expense(
        tenant_id=tenant_id,
        store_id=store_id,
        amount=25,
        status="approved",
        description="Store supplies",
        category="ops",
    )
    db_session.add(exp)
    await db_session.flush()
    await accounting_svc.post_journal_entry(
        db_session,
        tenant_id=tenant_id,
        user_id=seed["admin1"].id,
        description="Store supplies JE",
        source_type="expense",
        source_id=exp.id,
        lines=[
            {"account_code": "6000", "debit": 25, "credit": 0},
            {"account_code": "1000", "debit": 0, "credit": 25},
        ],
    )

    # Unlocated manual journal should be excluded when store filter is set
    await accounting_svc.post_journal_entry(
        db_session,
        tenant_id=tenant_id,
        user_id=seed["admin1"].id,
        description="HQ only JE",
        source_type="manual",
        lines=[
            {"account_code": "6000", "debit": 100, "credit": 0},
            {"account_code": "1000", "debit": 0, "credit": 100},
        ],
    )
    await db_session.commit()

    # Full TB (live) still includes everything in balances mode
    full = await ac.get("/api/v1/reports/trial-balance", headers=headers)
    assert full.status_code == 200, full.text

    filtered_tb = await ac.get(
        f"/api/v1/reports/trial-balance?store_id={store_id}",
        headers=headers,
    )
    assert filtered_tb.status_code == 200, filtered_tb.text
    tb = filtered_tb.json()["data"]
    assert tb["mode"] == "journals"
    assert tb["store_id"] == store_id
    expense_row = next((r for r in tb["rows"] if r["code"] == "6000"), None)
    assert expense_row is not None
    assert abs(float(expense_row["debit"]) - 25) < 0.01

    other_tb = await ac.get(
        f"/api/v1/reports/trial-balance?store_id={other_id}",
        headers=headers,
    )
    assert other_tb.status_code == 200
    other_data = other_tb.json()["data"]
    assert other_data["store_id"] == other_id
    assert not any(r["code"] == "6000" for r in other_data["rows"] or [])

    filtered_bs = await ac.get(
        f"/api/v1/reports/balance-sheet?store_id={store_id}",
        headers=headers,
    )
    assert filtered_bs.status_code == 200, filtered_bs.text
    bs = filtered_bs.json()["data"]
    assert bs["mode"] == "journals"
    assert bs["store_id"] == store_id
    # Retained earnings reflects store expense only (−25)
    re = next((r for r in bs["equity"] if r["code"] == "RE"), None)
    assert re is not None
    assert abs(float(re["balance"]) - (-25)) < 0.01
