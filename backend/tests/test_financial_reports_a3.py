"""Stage 3 A3: P&L date range + cash-flow operating/investing/financing."""

from __future__ import annotations

from datetime import datetime, timedelta

import pyotp
import pytest

from app import accounting as accounting_svc
from app import reports as reports_svc
from tests.conftest import auth_headers


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


async def _post_dated(db, *, tenant_id, user_id, when: datetime, **kwargs):
    entry = await accounting_svc.post_journal_entry(
        db, tenant_id=tenant_id, user_id=user_id, **kwargs
    )
    entry.entry_date = when
    await db.flush()
    return entry


@pytest.mark.asyncio
async def test_profit_loss_date_range_and_buckets(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)
    tenant_id = seed["t1"].id
    user_id = seed["admin1"].id
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)
    when = datetime(2026, 6, 15)

    await _post_dated(
        db_session,
        tenant_id=tenant_id,
        user_id=user_id,
        when=when,
        description="In-range sales",
        lines=[
            {"account_code": "1000", "debit": 200, "credit": 0},
            {"account_code": "4000", "debit": 0, "credit": 200},
        ],
        source_type="sales_invoice",
    )
    await _post_dated(
        db_session,
        tenant_id=tenant_id,
        user_id=user_id,
        when=when,
        description="In-range COGS",
        lines=[
            {"account_code": "5000", "debit": 70, "credit": 0},
            {"account_code": "1200", "debit": 0, "credit": 70},
        ],
        source_type="pos_sale",
    )
    await _post_dated(
        db_session,
        tenant_id=tenant_id,
        user_id=user_id,
        when=when,
        description="In-range opex",
        lines=[
            {"account_code": "6000", "debit": 30, "credit": 0},
            {"account_code": "1000", "debit": 0, "credit": 30},
        ],
        source_type="expense",
    )
    await _post_dated(
        db_session,
        tenant_id=tenant_id,
        user_id=user_id,
        when=datetime(2025, 1, 5),
        description="Outside range sales",
        lines=[
            {"account_code": "1000", "debit": 999, "credit": 0},
            {"account_code": "4000", "debit": 0, "credit": 999},
        ],
        source_type="sales_invoice",
    )
    await db_session.commit()

    r = await ac.get(
        "/api/v1/reports/profit-loss?from_date=2026-06-01&to_date=2026-06-30",
        headers=headers,
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["from_date"] == "2026-06-01"
    assert data["to_date"] == "2026-06-30"
    assert float(data["revenue"]) == 200
    assert float(data["cogs"]) == 70
    assert float(data["operating_expenses"]) == 30
    assert float(data["gross_profit"]) == 130
    assert float(data["net_profit"]) == 100
    buckets = {a["bucket"] for a in data["accounts"]}
    assert {"revenue", "cogs", "operating_expense"} <= buckets

    acct = await ac.get(
        "/api/v1/accounting/profit-loss?from_date=2026-06-01&to_date=2026-06-30",
        headers=headers,
    )
    assert acct.status_code == 200
    assert float(acct.json()["data"]["revenue"]) == 200


@pytest.mark.asyncio
async def test_profit_loss_excludes_unposted(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)
    tenant_id = seed["t1"].id
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)

    entry = await accounting_svc.post_journal_entry(
        db_session,
        tenant_id=tenant_id,
        user_id=seed["admin1"].id,
        description="Will unpost",
        lines=[
            {"account_code": "1000", "debit": 50, "credit": 0},
            {"account_code": "4000", "debit": 0, "credit": 50},
        ],
    )
    await db_session.commit()
    before = await ac.get("/api/v1/accounting/profit-loss", headers=headers)
    rev_before = float(before.json()["data"]["revenue"])

    await accounting_svc.unpost_journal_entry(
        db_session,
        tenant_id=tenant_id,
        user_id=seed["admin1"].id,
        entry_id=entry.id,
    )
    await db_session.commit()

    after = await ac.get("/api/v1/accounting/profit-loss", headers=headers)
    assert float(after.json()["data"]["revenue"]) == rev_before - 50


@pytest.mark.asyncio
async def test_cash_flow_oif_split_and_opening(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)
    tenant_id = seed["t1"].id
    user_id = seed["admin1"].id
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)

    await _post_dated(
        db_session,
        tenant_id=tenant_id,
        user_id=user_id,
        when=datetime(2026, 5, 1),
        description="Prior cash",
        lines=[
            {"account_code": "1000", "debit": 100, "credit": 0},
            {"account_code": "3900", "debit": 0, "credit": 100},
        ],
        source_type="opening_balance",
        source_id="seed-prior",
    )
    await _post_dated(
        db_session,
        tenant_id=tenant_id,
        user_id=user_id,
        when=datetime(2026, 6, 10),
        description="Cash sale",
        lines=[
            {"account_code": "1000", "debit": 40, "credit": 0},
            {"account_code": "4000", "debit": 0, "credit": 40},
        ],
        source_type="pos_sale",
    )

    cash = await accounting_svc.get_account_by_code(db_session, tenant_id, "1000")
    bank = await accounting_svc.get_account_by_code(db_session, tenant_id, "1010")
    xfer = await accounting_svc.transfer_liquid_funds(
        db_session,
        tenant_id=tenant_id,
        user_id=user_id,
        from_account_id=cash.id,
        to_account_id=bank.id,
        amount=25,
        kind="deposit",
    )
    xfer.entry_date = datetime(2026, 6, 12)
    await db_session.commit()

    r = await ac.get(
        "/api/v1/reports/cash-flow?from_date=2026-06-01&to_date=2026-06-30",
        headers=headers,
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert float(data["opening_cash"]) == 100
    assert float(data["operating"]["net"]) == 40
    assert float(data["financing"]["net"]) == 0
    assert float(data["transfers"]["inflows"]) == 25
    assert float(data["transfers"]["outflows"]) == 25
    assert float(data["transfers"]["net"]) == 0
    assert float(data["net_change"]) == 40
    assert float(data["closing_cash"]) == 140
    activities = {ln["activity"] for ln in data["lines"]}
    assert "operating" in activities
    assert "transfer" in activities


@pytest.mark.asyncio
async def test_classify_cash_flow_activity_helpers():
    assert reports_svc.classify_cash_flow_activity("pos_sale") == "operating"
    assert reports_svc.classify_cash_flow_activity("opening_balance") == "financing"
    assert reports_svc.classify_cash_flow_activity("liquid_deposit") == "transfer"
    assert reports_svc.classify_cash_flow_activity(None) == "operating"


@pytest.mark.asyncio
async def test_profit_loss_export_respects_dates(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)
    tenant_id = seed["t1"].id
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)
    entry = await accounting_svc.post_journal_entry(
        db_session,
        tenant_id=tenant_id,
        user_id=seed["admin1"].id,
        description="Export window",
        lines=[
            {"account_code": "1000", "debit": 12, "credit": 0},
            {"account_code": "4000", "debit": 0, "credit": 12},
        ],
    )
    entry.entry_date = datetime.utcnow() - timedelta(days=3)
    await db_session.commit()

    day = entry.entry_date.date().isoformat()
    r = await ac.get(
        f"/api/v1/reports/export?report_type=profit_loss&format=csv&from_date={day}&to_date={day}",
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert "4000" in r.text or "Sales" in r.text
