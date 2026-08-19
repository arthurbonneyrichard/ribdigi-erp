"""Stage 23 F1: balance sheet / P&L / cash-flow store and branch filters."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pyotp
import pytest

from app import accounting as accounting_svc
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


async def _post_dated(db, *, tenant_id, user_id, when: datetime, store_id=None, **kwargs):
    entry = await accounting_svc.post_journal_entry(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        store_id=store_id,
        **kwargs,
    )
    entry.entry_date = when
    await db.flush()
    return entry


@pytest.mark.asyncio
async def test_balance_sheet_store_and_branch_filters(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)
    tenant_id = seed["t1"].id
    user_id = seed["admin1"].id
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)

    branch_a = await ac.post(
        "/api/v1/branches",
        headers=headers,
        json={"code": "F1BA", "name": "F1 Branch A"},
    )
    assert branch_a.status_code == 200, branch_a.text
    branch_a_id = branch_a.json()["data"]["id"]

    branch_b = await ac.post(
        "/api/v1/branches",
        headers=headers,
        json={"code": "F1BB", "name": "F1 Branch B"},
    )
    assert branch_b.status_code == 200, branch_b.text
    branch_b_id = branch_b.json()["data"]["id"]

    store_a = await ac.post(
        "/api/v1/stores",
        headers=headers,
        json={"code": "F1SA", "name": "F1 Store A", "branch_id": branch_a_id},
    )
    assert store_a.status_code == 200, store_a.text
    store_a_id = store_a.json()["data"]["id"]

    store_b = await ac.post(
        "/api/v1/stores",
        headers=headers,
        json={"code": "F1SB", "name": "F1 Store B", "branch_id": branch_b_id},
    )
    assert store_b.status_code == 200, store_b.text
    store_b_id = store_b.json()["data"]["id"]

    when = datetime(2026, 6, 15, 12, 0, 0)
    await _post_dated(
        db_session,
        tenant_id=tenant_id,
        user_id=user_id,
        when=when,
        store_id=store_a_id,
        description="Store A sale",
        lines=[
            {"account_code": "1000", "debit": 100, "credit": 0},
            {"account_code": "4000", "debit": 0, "credit": 100},
        ],
        source_type="sales_invoice",
    )
    await _post_dated(
        db_session,
        tenant_id=tenant_id,
        user_id=user_id,
        when=when,
        store_id=store_b_id,
        description="Store B sale",
        lines=[
            {"account_code": "1000", "debit": 40, "credit": 0},
            {"account_code": "4000", "debit": 0, "credit": 40},
        ],
        source_type="sales_invoice",
    )
    await db_session.commit()

    bs_a = await ac.get(
        "/api/v1/reports/balance-sheet",
        headers=headers,
        params={"as_of_date": "2026-06-30", "store_id": store_a_id},
    )
    assert bs_a.status_code == 200, bs_a.text
    data_a = bs_a.json()["data"]
    assert data_a["store_id"] == store_a_id
    assert data_a["balanced"] is True
    cash_a = next(r for r in data_a["assets"] if r["code"] == "1000")
    assert float(cash_a["balance"]) == pytest.approx(100)

    bs_b = await ac.get(
        "/api/v1/reports/balance-sheet",
        headers=headers,
        params={"as_of_date": "2026-06-30", "store_id": store_b_id},
    )
    assert bs_b.status_code == 200, bs_b.text
    cash_b = next(r for r in bs_b.json()["data"]["assets"] if r["code"] == "1000")
    assert float(cash_b["balance"]) == pytest.approx(40)

    bs_branch = await ac.get(
        "/api/v1/reports/balance-sheet",
        headers=headers,
        params={"as_of_date": "2026-06-30", "branch_id": branch_a_id},
    )
    assert bs_branch.status_code == 200, bs_branch.text
    data_br = bs_branch.json()["data"]
    assert data_br["branch_id"] == branch_a_id
    cash_br = next(r for r in data_br["assets"] if r["code"] == "1000")
    assert float(cash_br["balance"]) == pytest.approx(100)

    empty_branch = await ac.post(
        "/api/v1/branches",
        headers=headers,
        json={"code": "F1BE", "name": "F1 Empty Branch"},
    )
    empty_id = empty_branch.json()["data"]["id"]
    bs_empty = await ac.get(
        "/api/v1/reports/balance-sheet",
        headers=headers,
        params={"branch_id": empty_id},
    )
    assert bs_empty.status_code == 200, bs_empty.text
    empty_data = bs_empty.json()["data"]
    assert empty_data["branch_id"] == empty_id
    assert float(empty_data["total_assets"]) == pytest.approx(0)
    assert empty_data["balanced"] is True

    foreign = await ac.get(
        "/api/v1/reports/balance-sheet",
        headers=headers,
        params={"store_id": "nonexistent-store"},
    )
    assert foreign.status_code == 404

    mismatch = await ac.get(
        "/api/v1/reports/balance-sheet",
        headers=headers,
        params={"store_id": store_a_id, "branch_id": branch_b_id},
    )
    assert mismatch.status_code == 400
    assert "STORE_BRANCH_MISMATCH" in str(mismatch.json()["detail"])

    # P&L / cash-flow branch parity
    pnl = await ac.get(
        "/api/v1/reports/profit-loss",
        headers=headers,
        params={
            "from_date": "2026-06-01",
            "to_date": "2026-06-30",
            "branch_id": branch_a_id,
        },
    )
    assert pnl.status_code == 200, pnl.text
    assert pnl.json()["data"]["branch_id"] == branch_a_id
    assert float(pnl.json()["data"]["revenue"]) == pytest.approx(100)

    cf = await ac.get(
        "/api/v1/reports/cash-flow",
        headers=headers,
        params={
            "from_date": "2026-06-01",
            "to_date": "2026-06-30",
            "store_id": store_b_id,
        },
    )
    assert cf.status_code == 200, cf.text
    assert cf.json()["data"]["store_id"] == store_b_id
    assert float(cf.json()["data"]["inflows"]) == pytest.approx(40)

    # Export passes store filter
    export = await ac.get(
        "/api/v1/reports/export",
        headers=headers,
        params={
            "report_type": "balance_sheet",
            "format": "csv",
            "as_of_date": "2026-06-30",
            "store_id": store_a_id,
        },
    )
    assert export.status_code == 200, export.text
    assert "1000" in export.text


def test_financial_report_filters_f1_docs_synced():
    br = (ROOT / "docs" / "BUSINESS_REQUIREMENTS_DOCUMENT.md").read_text(encoding="utf-8")
    s145 = br.split("#### BR-14.5 Financial Reports")[1].split("---")[0]
    assert "Stage 23 F1" in s145
    assert "[x] All reports filterable by date range, branch, store" in s145

    plan = (ROOT / "docs" / "STAGE_23_PLAN.md").read_text(encoding="utf-8")
    f1 = [ln for ln in plan.splitlines() if "| **F1**" in ln][0]
    assert "COMPLETE" in f1
    assert "test_financial_report_filters_f1.py" in plan

    launch = (ROOT / "docs" / "LAUNCH_CHECKLIST.md").read_text(encoding="utf-8")
    assert "test_financial_report_filters_f1.py" in launch
    assert "ADR-051" in launch or "ADR_051" in launch

    api = (ROOT / "docs" / "API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "balance-sheet" in api
    assert "branch_id" in api
    assert "Stage 23 F1" in api

    manual = (ROOT / "docs" / "USER_MANUAL.md").read_text(encoding="utf-8")
    assert "Stage 23" in manual or "branch" in manual.lower()
