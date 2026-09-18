"""Trial balance store/branch filters (Stage 23 F1 leftover on TB APIs)."""

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
async def test_trial_balance_store_and_branch_filters(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)
    tenant_id = seed["t1"].id
    company_id = seed["c1"].id
    user_id = seed["admin1"].id
    await accounting_svc.ensure_default_accounts(
        db_session, tenant_id, company_id=company_id
    )

    branch_a = await ac.post(
        "/api/v1/branches",
        headers=headers,
        json={"code": "TBT1A", "name": "TB Filter Branch A"},
    )
    assert branch_a.status_code == 200, branch_a.text
    branch_a_id = branch_a.json()["data"]["id"]

    branch_b = await ac.post(
        "/api/v1/branches",
        headers=headers,
        json={"code": "TBT1B", "name": "TB Filter Branch B"},
    )
    assert branch_b.status_code == 200, branch_b.text
    branch_b_id = branch_b.json()["data"]["id"]

    store_a = await ac.post(
        "/api/v1/stores",
        headers=headers,
        json={"code": "TBT1SA", "name": "TB Filter Store A", "branch_id": branch_a_id},
    )
    assert store_a.status_code == 200, store_a.text
    store_a_id = store_a.json()["data"]["id"]

    store_b = await ac.post(
        "/api/v1/stores",
        headers=headers,
        json={"code": "TBT1SB", "name": "TB Filter Store B", "branch_id": branch_b_id},
    )
    assert store_b.status_code == 200, store_b.text
    store_b_id = store_b.json()["data"]["id"]

    when = datetime(2026, 6, 15, 12, 0, 0)
    await _post_dated(
        db_session,
        tenant_id=tenant_id,
        user_id=user_id,
        company_id=company_id,
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
        company_id=company_id,
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

    tb_a = await ac.get(
        "/api/v1/accounting/trial-balance",
        headers=headers,
        params={"as_of_date": "2026-06-30", "store_id": store_a_id},
    )
    assert tb_a.status_code == 200, tb_a.text
    data_a = tb_a.json()["data"]
    assert data_a["store_id"] == store_a_id
    assert data_a["branch_id"] is None
    assert data_a["as_of"] == "2026-06-30"
    assert data_a["balanced"] is True
    by_code_a = {r["code"]: r for r in data_a["rows"]}
    assert float(by_code_a["1000"]["debit"]) == pytest.approx(100)
    assert float(by_code_a["4000"]["credit"]) == pytest.approx(100)

    tb_b = await ac.get(
        "/api/v1/reports/trial-balance",
        headers=headers,
        params={"as_of_date": "2026-06-30", "store_id": store_b_id},
    )
    assert tb_b.status_code == 200, tb_b.text
    data_b = tb_b.json()["data"]
    assert data_b["store_id"] == store_b_id
    by_code_b = {r["code"]: r for r in data_b["rows"]}
    assert float(by_code_b["1000"]["debit"]) == pytest.approx(40)
    assert float(by_code_b["4000"]["credit"]) == pytest.approx(40)

    tb_branch = await ac.get(
        "/api/v1/accounting/trial-balance",
        headers=headers,
        params={"as_of_date": "2026-06-30", "branch_id": branch_a_id},
    )
    assert tb_branch.status_code == 200, tb_branch.text
    data_br = tb_branch.json()["data"]
    assert data_br["branch_id"] == branch_a_id
    by_code_br = {r["code"]: r for r in data_br["rows"]}
    assert float(by_code_br["1000"]["debit"]) == pytest.approx(100)

    empty_branch = await ac.post(
        "/api/v1/branches",
        headers=headers,
        json={"code": "TBT1E", "name": "TB Filter Empty Branch"},
    )
    empty_id = empty_branch.json()["data"]["id"]
    tb_empty = await ac.get(
        "/api/v1/accounting/trial-balance",
        headers=headers,
        params={"branch_id": empty_id},
    )
    assert tb_empty.status_code == 200, tb_empty.text
    empty_data = tb_empty.json()["data"]
    assert empty_data["branch_id"] == empty_id
    assert float(empty_data["total_debit"]) == pytest.approx(0)
    assert float(empty_data["total_credit"]) == pytest.approx(0)
    assert empty_data["balanced"] is True

    foreign = await ac.get(
        "/api/v1/accounting/trial-balance",
        headers=headers,
        params={"store_id": "nonexistent-store"},
    )
    assert foreign.status_code == 404

    mismatch = await ac.get(
        "/api/v1/accounting/trial-balance",
        headers=headers,
        params={"store_id": store_a_id, "branch_id": branch_b_id},
    )
    assert mismatch.status_code == 400
    assert "STORE_BRANCH_MISMATCH" in str(mismatch.json()["detail"])

    exported = await ac.get(
        "/api/v1/accounting/trial-balance/export",
        headers=headers,
        params={"as_of_date": "2026-06-30", "store_id": store_a_id},
    )
    assert exported.status_code == 200, exported.text
    header = exported.text.splitlines()[0]
    assert "store_id" in header
    assert "branch_id" in header
    assert store_a_id in exported.text
    assert "1000" in exported.text

    reports_export = await ac.get(
        "/api/v1/reports/export",
        headers=headers,
        params={
            "report_type": "trial_balance",
            "format": "csv",
            "as_of_date": "2026-06-30",
            "store_id": store_a_id,
        },
    )
    assert reports_export.status_code == 200, reports_export.text
    assert "1000" in reports_export.text


def test_trial_balance_store_filter_docs_and_ui():
    api_doc = ROOT / "docs" / "API_DOCUMENTATION.md"
    accounting_page = ROOT / "frontend/app/accounting/page.tsx"
    reports_page = ROOT / "frontend/app/reports/page.tsx"
    if not api_doc.exists() or not accounting_page.exists():
        pytest.skip("repo docs/UI not mounted in this test image")

    api = api_doc.read_text(encoding="utf-8")
    assert "trial-balance?as_of_date=&store_id=&branch_id=" in api

    page = accounting_page.read_text(encoding="utf-8")
    assert "Trial balance store filter" in page
    assert "tbStoreId" in page

    if reports_page.exists():
        reports = reports_page.read_text(encoding="utf-8")
        assert "/reports/trial-balance/export" in reports
        assert "params.set('store_id', storeId)" in reports
