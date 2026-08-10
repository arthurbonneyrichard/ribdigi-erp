"""Stage 23 I1: isolation matrix residual coverage for finance/report surfaces."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pyotp
import pytest
from sqlalchemy import select

from app import accounting as accounting_svc
from app import expenses as expenses_svc
from app import models as m
from app import stores as stores_svc
from tests.conftest import auth_headers

pytestmark = pytest.mark.isolation

ROOT = Path(__file__).resolve().parents[2]


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_foreign_liquid_account_and_transfer_404(client, db_session):
    ac, seed = client
    foreign = await accounting_svc.create_liquid_account(
        db_session,
        tenant_id=seed["t2"].id,
        kind="cash",
        code="I1CASH",
        name="Beta Petty Cash",
    )
    await db_session.commit()

    headers = await _super(ac, seed)
    listed = await ac.get("/api/v1/accounting/liquid-accounts", headers=headers)
    assert listed.status_code == 200
    codes = {row.get("code") for row in listed.json()["data"]}
    assert "I1CASH" not in codes

    patch = await ac.patch(
        f"/api/v1/accounting/liquid-accounts/{foreign.id}",
        headers=headers,
        json={"name": "Hijacked"},
    )
    assert patch.status_code == 404

    # Own cash account + foreign counterpart on transfer
    own_cash = await accounting_svc.create_liquid_account(
        db_session,
        tenant_id=seed["t1"].id,
        kind="cash",
        code="I1OWNC",
        name="Alpha Petty",
    )
    await db_session.commit()
    xfer = await ac.post(
        "/api/v1/accounting/liquid-transfers",
        headers=headers,
        json={
            "from_account_id": own_cash.id,
            "to_account_id": foreign.id,
            "amount": 5,
            "kind": "transfer",
        },
    )
    assert xfer.status_code == 404


@pytest.mark.asyncio
async def test_foreign_expense_category_and_recurring_404(client, db_session):
    ac, seed = client
    await expenses_svc.ensure_default_categories(db_session, seed["t2"].id)
    await db_session.commit()
    cats = (
        await db_session.execute(
            select(m.ExpenseCategory).where(m.ExpenseCategory.tenant_id == seed["t2"].id)
        )
    ).scalars().all()
    assert cats
    foreign_cat = cats[0]

    rec = m.RecurringExpense(
        tenant_id=seed["t2"].id,
        category_id=foreign_cat.id,
        category=foreign_cat.name,
        description="Beta rent",
        amount=100,
        frequency="monthly",
        payment_method="bank_transfer",
        start_date=datetime(2026, 1, 1),
        next_run_at=datetime(2026, 2, 1),
        created_by=seed["u2"].id,
    )
    db_session.add(rec)
    await db_session.commit()

    headers = await _super(ac, seed)
    cats_r = await ac.get("/api/v1/expenses/categories", headers=headers)
    assert cats_r.status_code == 200
    cat_ids = {row["id"] for row in cats_r.json()["data"]}
    assert foreign_cat.id not in cat_ids

    patch_cat = await ac.patch(
        f"/api/v1/expenses/categories/{foreign_cat.id}",
        headers=headers,
        json={"budget_amount": 999},
    )
    assert patch_cat.status_code == 404

    listed = await ac.get("/api/v1/expenses/recurring", headers=headers)
    assert listed.status_code == 200
    rec_ids = {row["id"] for row in listed.json()["data"]}
    assert rec.id not in rec_ids

    patch_rec = await ac.patch(
        f"/api/v1/expenses/recurring/{rec.id}",
        headers=headers,
        json={"skip_next": True},
    )
    assert patch_rec.status_code == 404


@pytest.mark.asyncio
async def test_foreign_branch_and_report_dimension_404(client, db_session):
    ac, seed = client
    branch = m.Branch(
        tenant_id=seed["t2"].id,
        code="I1BB",
        name="Beta Branch",
    )
    db_session.add(branch)
    await db_session.flush()
    store = await stores_svc.create_store(
        db_session,
        tenant_id=seed["t2"].id,
        name="Beta Store I1",
        code="I1BS",
        branch_id=branch.id,
    )
    await db_session.commit()

    headers = await _super(ac, seed)
    branch_patch = await ac.patch(
        f"/api/v1/branches/{branch.id}",
        headers=headers,
        json={"name": "Hijacked Branch"},
    )
    assert branch_patch.status_code == 404

    for path in (
        "/api/v1/reports/balance-sheet",
        "/api/v1/reports/profit-loss",
        "/api/v1/reports/cash-flow",
    ):
        store_r = await ac.get(path, headers=headers, params={"store_id": store.id})
        assert store_r.status_code == 404, path
        branch_r = await ac.get(path, headers=headers, params={"branch_id": branch.id})
        assert branch_r.status_code == 404, path


@pytest.mark.asyncio
async def test_mismatched_tenant_header_on_financial_reports(client):
    ac, seed = client
    headers = await _super(ac, seed)
    bad = {**headers, "X-Tenant-ID": seed["t2"].id}

    for path in (
        "/api/v1/reports/balance-sheet",
        "/api/v1/reports/profit-loss",
        "/api/v1/reports/cash-flow",
        "/api/v1/accounting/liquid-accounts",
        "/api/v1/expenses/budgets",
    ):
        r = await ac.get(path, headers=bad)
        assert r.status_code == 403, path


def test_isolation_matrix_i1_docs():
    plan = (ROOT / "docs/STAGE_23_PLAN.md").read_text(encoding="utf-8")
    line = [ln for ln in plan.splitlines() if "| **I1**" in ln][0]
    assert "COMPLETE" in line
    assert "test_isolation_matrix_i1.py" in plan

    pr = (ROOT / "PRODUCTION_READINESS.md").read_text(encoding="utf-8")
    assert "Stage 23 I1" in pr
    assert "test_isolation_matrix_i1.py" in pr

    sec = (ROOT / "docs/SECURITY_GUIDE.md").read_text(encoding="utf-8")
    assert "Stage 23 I1" in sec or "test_isolation_matrix_i1.py" in sec

    launch = (ROOT / "docs/LAUNCH_CHECKLIST.md").read_text(encoding="utf-8")
    assert "test_isolation_matrix_i1.py" in launch
