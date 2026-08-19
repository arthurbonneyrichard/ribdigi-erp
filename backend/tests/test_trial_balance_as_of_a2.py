"""Stage 14 A2: point-in-time trial balance and balance sheet via as_of_date."""

from __future__ import annotations

from datetime import datetime

import pyotp
import pytest

from app import accounting as accounting_svc
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
async def test_trial_balance_and_balance_sheet_as_of(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)
    tenant_id = seed["t1"].id
    user_id = seed["admin1"].id
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)

    # Early period: cash +100 / revenue +100
    await _post_dated(
        db_session,
        tenant_id=tenant_id,
        user_id=user_id,
        when=datetime(2026, 3, 10, 12, 0, 0),
        description="March sale",
        lines=[
            {"account_code": "1000", "debit": 100, "credit": 0},
            {"account_code": "4000", "debit": 0, "credit": 100},
        ],
        source_type="sales_invoice",
    )
    # Later period: opex 40 / cash -40 (should be excluded from March as_of)
    await _post_dated(
        db_session,
        tenant_id=tenant_id,
        user_id=user_id,
        when=datetime(2026, 5, 20, 12, 0, 0),
        description="May expense",
        lines=[
            {"account_code": "6000", "debit": 40, "credit": 0},
            {"account_code": "1000", "debit": 0, "credit": 40},
        ],
        source_type="expense",
    )
    await db_session.commit()

    tb_march = await ac.get(
        "/api/v1/accounting/trial-balance",
        headers=headers,
        params={"as_of_date": "2026-03-31"},
    )
    assert tb_march.status_code == 200, tb_march.text
    tdata = tb_march.json()["data"]
    assert tdata["as_of"] == "2026-03-31"
    assert tdata["balanced"] is True
    by_code = {r["code"]: r for r in tdata["rows"]}
    assert float(by_code["1000"]["debit"]) == pytest.approx(100)
    assert float(by_code["4000"]["credit"]) == pytest.approx(100)
    assert float(by_code["6000"]["debit"]) == pytest.approx(0)
    assert float(by_code["6000"]["credit"]) == pytest.approx(0)

    tb_may = await ac.get(
        "/api/v1/reports/trial-balance",
        headers=headers,
        params={"as_of_date": "2026-05-31"},
    )
    assert tb_may.status_code == 200, tb_may.text
    mdata = tb_may.json()["data"]
    assert mdata["as_of"] == "2026-05-31"
    m_by = {r["code"]: r for r in mdata["rows"]}
    assert float(m_by["1000"]["debit"]) == pytest.approx(60)
    assert float(m_by["6000"]["debit"]) == pytest.approx(40)

    bs_march = await ac.get(
        "/api/v1/reports/balance-sheet",
        headers=headers,
        params={"as_of_date": "2026-03-31"},
    )
    assert bs_march.status_code == 200, bs_march.text
    bdata = bs_march.json()["data"]
    assert bdata["as_of"] == "2026-03-31"
    assert bdata["balanced"] is True
    cash_row = next(r for r in bdata["assets"] if r["code"] == "1000")
    assert float(cash_row["balance"]) == pytest.approx(100)
    # May expense must not reduce March assets
    assert float(bdata["total_assets"]) == pytest.approx(100)

    bs_may = await ac.get(
        "/api/v1/reports/balance-sheet",
        headers=headers,
        params={"as_of_date": "2026-05-31"},
    )
    assert bs_may.status_code == 200, bs_may.text
    bmay = bs_may.json()["data"]
    cash_may = next(r for r in bmay["assets"] if r["code"] == "1000")
    assert float(cash_may["balance"]) == pytest.approx(60)
    # Retained = income 100 - expense 40
    re = next(r for r in bmay["equity"] if r["code"] == "RE")
    assert float(re["balance"]) == pytest.approx(60)

    # Current (no as_of) still returns as_of and includes all posted activity
    tb_now = await ac.get("/api/v1/accounting/trial-balance", headers=headers)
    assert tb_now.status_code == 200, tb_now.text
    now_data = tb_now.json()["data"]
    assert "as_of" in now_data
    now_by = {r["code"]: r for r in now_data["rows"]}
    assert float(now_by["6000"]["debit"]) == pytest.approx(40)
