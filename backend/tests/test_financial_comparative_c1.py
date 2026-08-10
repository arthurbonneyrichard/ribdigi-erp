"""Stage 23 C1: financial comparative P&L / cash-flow / balance sheet."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pyotp
import pytest

from app import accounting as accounting_svc
from app import reports as reports_svc
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


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
async def test_financial_comparative_pnl_cashflow_balance_sheet(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)
    tenant_id = seed["t1"].id
    user_id = seed["admin1"].id
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)

    # Prior month (May): revenue 80
    await _post_dated(
        db_session,
        tenant_id=tenant_id,
        user_id=user_id,
        when=datetime(2026, 5, 10, 12, 0, 0),
        description="May sale",
        lines=[
            {"account_code": "1000", "debit": 80, "credit": 0},
            {"account_code": "4000", "debit": 0, "credit": 80},
        ],
        source_type="sales_invoice",
    )
    # Current month (June): revenue 100
    await _post_dated(
        db_session,
        tenant_id=tenant_id,
        user_id=user_id,
        when=datetime(2026, 6, 12, 12, 0, 0),
        description="June sale",
        lines=[
            {"account_code": "1000", "debit": 100, "credit": 0},
            {"account_code": "4000", "debit": 0, "credit": 100},
        ],
        source_type="sales_invoice",
    )
    await db_session.commit()

    pnl = await ac.get(
        "/api/v1/reports/profit-loss",
        headers=headers,
        params={
            "from_date": "2026-06-01",
            "to_date": "2026-06-30",
            "compare": "true",
        },
    )
    assert pnl.status_code == 200, pnl.text
    pdata = pnl.json()["data"]
    assert float(pdata["revenue"]) == pytest.approx(100)
    assert "comparison" in pdata
    assert pdata["comparison"]["mode"] == "prior_period"
    assert pdata["comparison"]["from_date"] == "2026-05-02"
    assert pdata["comparison"]["to_date"] == "2026-05-31"
    rev = pdata["comparison"]["metrics"]["revenue"]
    assert float(rev["current"]) == pytest.approx(100)
    assert float(rev["prior"]) == pytest.approx(80)
    assert float(rev["change_pct"]) == pytest.approx(25.0)

    cf = await ac.get(
        "/api/v1/reports/cash-flow",
        headers=headers,
        params={
            "from_date": "2026-06-01",
            "to_date": "2026-06-30",
            "compare": "true",
        },
    )
    assert cf.status_code == 200, cf.text
    cdata = cf.json()["data"]
    assert "comparison" in cdata
    assert float(cdata["inflows"]) == pytest.approx(100)
    assert float(cdata["comparison"]["metrics"]["inflows"]["prior"]) == pytest.approx(80)

    bs = await ac.get(
        "/api/v1/reports/balance-sheet",
        headers=headers,
        params={"as_of_date": "2026-06-30", "compare": "true"},
    )
    assert bs.status_code == 200, bs.text
    bdata = bs.json()["data"]
    assert "comparison" in bdata
    assert bdata["comparison"]["mode"] == "prior_as_of"
    assert bdata["comparison"]["as_of"] == "2026-05-30"
    assets = bdata["comparison"]["metrics"]["total_assets"]
    assert float(assets["current"]) > float(assets["prior"])
    assert assets["change_pct"] is not None

    # Without compare, no comparison block
    plain = await ac.get(
        "/api/v1/reports/profit-loss",
        headers=headers,
        params={"from_date": "2026-06-01", "to_date": "2026-06-30"},
    )
    assert plain.status_code == 200
    assert "comparison" not in plain.json()["data"]

    export = await ac.get(
        "/api/v1/reports/export",
        headers=headers,
        params={
            "report_type": "profit_loss",
            "format": "csv",
            "from_date": "2026-06-01",
            "to_date": "2026-06-30",
            "compare": "true",
        },
    )
    assert export.status_code == 200, export.text
    assert "change_pct" in export.text or "comparison" in export.text.lower() or "25" in export.text


def test_prior_period_helpers():
    start = datetime(2026, 6, 1)
    end = datetime(2026, 6, 30, 23, 59, 59, 999999)
    p_from, p_to = reports_svc.prior_period_bounds(start, end)
    assert p_from.date().isoformat() == "2026-05-02"
    assert p_to.date().isoformat() == "2026-05-31"
    prior = reports_svc.prior_as_of_date(datetime(2026, 6, 30, 23, 59, 59))
    assert prior.date().isoformat() == "2026-05-30"
    assert reports_svc.metric_change_pct(100, 80) == 25.0
    assert reports_svc.metric_change_pct(10, 0) is None


def test_financial_comparative_c1_docs_synced():
    br = (ROOT / "docs" / "BUSINESS_REQUIREMENTS_DOCUMENT.md").read_text(encoding="utf-8")
    s145 = br.split("#### BR-14.5 Financial Reports")[1].split("---")[0]
    assert "Stage 23 C1" in s145
    assert "full financial comparative deferred" not in s145

    plan = (ROOT / "docs" / "STAGE_23_PLAN.md").read_text(encoding="utf-8")
    c1 = [ln for ln in plan.splitlines() if "| **C1**" in ln][0]
    assert "COMPLETE" in c1
    assert "test_financial_comparative_c1.py" in plan

    launch = (ROOT / "docs" / "LAUNCH_CHECKLIST.md").read_text(encoding="utf-8")
    assert "test_financial_comparative_c1.py" in launch

    api = (ROOT / "docs" / "API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "compare" in api
    assert "Stage 23 C1" in api
